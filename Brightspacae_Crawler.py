cookie = '' # copy Ur cookie, find in F12 dev mode
course_id = 436017 # Find Course id in the url link in Brightspace, e.g. brightspace.nyu.edu/d2l/home/438396

import re
from tempfile import TemporaryDirectory
import os
import requests
import zipfile
from urllib.parse import unquote

def get_course_name():
    url = f"https://brightspace.nyu.edu/d2l/home/{course_id}"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36',
        'Cookie': f'{cookie}'
    }
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        title_match = re.search(r'<title>(.*?)</title>', response.text, re.IGNORECASE)
        if title_match:
            full_title = title_match.group(1).strip()
            return full_title.split('Brightspace - ')[-1]
        return None

    except requests.exceptions.RequestException as e:
        print(f"Error fetching course name: {e}")
        return None


def sanitize_folder_name(name):
    sanitized = re.sub(r'[\\/*?:"<>|]', '_', name)
    sanitized = sanitized.strip().rstrip('.')
    if not sanitized:
        sanitized = "Untitled Folder"
    return sanitized


def get_all_topic_ids(course_id):
    url = f"https://brightspace.nyu.edu/d2l/api/le/unstable/{course_id}/content/toc?loadDescription=true"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36',
        'referer': f'https://brightspace.nyu.edu/d2l/home/{course_id}',
        'Cookie': f'{cookie}'
    }
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        data = response.json()

        topic_info = []  # List of tuples (topic_id, path)

        def extract_topics(modules, current_path):
            for module in modules:
                module_title = module.get('Title', 'Untitled Module')
                sanitized_title = sanitize_folder_name(module_title)
                new_path = current_path + [sanitized_title]
                # Add topics from current module
                for topic in module.get('Topics', []):
                    if 'TopicId' in topic:
                        topic_info.append((topic['TopicId'], new_path))
                # Recursively process nested modules
                if 'Modules' in module and module['Modules']:
                    extract_topics(module['Modules'], new_path)

        if 'Modules' in data:
            extract_topics(data['Modules'], current_path=[])

        return topic_info

    except requests.exceptions.RequestException as e:
        print(f"Error fetching data: {e}")
        return []
    except ValueError as e:
        print(f"Error parsing JSON: {e}")
        return []


def download_files(course_id, topic_info):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36',
        'referer': 'https://brightspace.nyu.edu/d2l/ui/apps/smart-curriculum/3.11.23/index.html',
        'Cookie': f'{cookie}'
    }

    with TemporaryDirectory() as temp_dir:
        downloaded_files = []

        for topic_id, path in topic_info:
            url = f"https://brightspace.nyu.edu/d2l/le/content/{course_id}/topics/files/download/{topic_id}/DirectFileTopicDownload"
            try:
                with requests.get(url, headers=headers, stream=True) as response:
                    if response.status_code == 200:
                        content_disposition = response.headers.get('content-disposition', '')
                        filename = 'unknown_file'
                        if 'filename=' in content_disposition:
                            filename = content_disposition.split('filename=')[-1].strip('"')
                            filename = unquote(unquote(filename))
                            filename = os.path.basename(filename)
                            filename = filename.split(';')[0]

                        # Create directory structure
                        dir_path = os.path.join(temp_dir, *path)
                        os.makedirs(dir_path, exist_ok=True)

                        # Handle duplicate filenames
                        base, ext = os.path.splitext(filename)
                        counter = 1
                        file_path = os.path.join(dir_path, filename)
                        while os.path.exists(file_path):
                            file_path = os.path.join(dir_path, f"{base}_{counter}{ext}")
                            counter += 1

                        # Save the file
                        with open(file_path, 'wb') as f:
                            for chunk in response.iter_content(chunk_size=8192):
                                if chunk:
                                    f.write(chunk)
                        downloaded_files.append(file_path)
                        print(f"Downloaded: {os.path.join(*path, filename)}")
                    else:
                        print(f"Skipping topic {topic_id} - Status: {response.status_code}")

            except Exception as e:
                print(f"Error downloading topic {topic_id}: {str(e)}")

        if downloaded_files:
            course_name = get_course_name()
            zip_filename = f"{course_name}_{course_id}_files.zip"
            with zipfile.ZipFile(zip_filename, 'w') as zipf:
                for file in downloaded_files:
                    arcname = os.path.relpath(file, temp_dir)
                    zipf.write(file, arcname)
            print(f"\nSuccessfully created zip file: {zip_filename}")
            return zip_filename
        else:
            print("No files were downloaded")
            return None


topic_info = get_all_topic_ids(course_id)

if topic_info:
    print(f"Found {len(topic_info)} topics, attempting downloads...")
    zip_file = download_files(course_id, topic_info)
else:
    print("No topics found")
