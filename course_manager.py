import os
import json
import shutil
from datetime import datetime

class CourseManager:
    def __init__(self, base_dir="scholar_data"):
        self.base_dir = base_dir
        self.courses_dir = os.path.join(self.base_dir, "courses")
        os.makedirs(self.courses_dir, exist_ok=True)

    def create_course(self, course_name):
        safe_name = course_name.replace(" ", "_").lower()
        course_path = os.path.join(self.courses_dir, safe_name)
        
        if not os.path.exists(course_path):
            os.makedirs(course_path)
            os.makedirs(os.path.join(course_path, "raw_files"))
            os.makedirs(os.path.join(course_path, "chroma_db"))
            os.makedirs(os.path.join(course_path, "chat_logs")) 
            
            meta = {"name": course_name, "safe_name": safe_name, "created_at": str(datetime.now())}
            with open(os.path.join(course_path, "meta.json"), "w") as f:
                json.dump(meta, f)
            return True
        return False

    def list_courses(self):
        courses = []
        for folder in os.listdir(self.courses_dir):
            meta_path = os.path.join(self.courses_dir, folder, "meta.json")
            if os.path.exists(meta_path):
                with open(meta_path, "r") as f:
                    meta = json.load(f)
                    courses.append(meta["name"])
        return courses

    def get_course_db_path(self, course_name):
        safe_name = course_name.replace(" ", "_").lower()
        return os.path.join(self.courses_dir, safe_name, "chroma_db")

    def list_course_files(self, course_name):
        safe_name = course_name.replace(" ", "_").lower()
        raw_files_dir = os.path.join(self.courses_dir, safe_name, "raw_files")
        if os.path.exists(raw_files_dir):
            return os.listdir(raw_files_dir)
        return []

    def export_course_zip(self, course_name, destination_path):
        safe_name = course_name.replace(" ", "_").lower()
        course_path = os.path.join(self.courses_dir, safe_name)
        base_dest = destination_path.replace(".zip", "")
        try:
            shutil.make_archive(base_dest, 'zip', course_path)
            return True
        except Exception as e:
            print(f"Zip Error: {e}")
            return False

    def import_course_zip(self, zip_path):
        temp_dir = os.path.join(self.base_dir, "temp_import")
        os.makedirs(temp_dir, exist_ok=True)
        try:
            shutil.unpack_archive(zip_path, temp_dir)
            meta_path = os.path.join(temp_dir, "meta.json")
            if not os.path.exists(meta_path):
                shutil.rmtree(temp_dir)
                return False, "Invalid Course Archive: meta.json missing."
                
            with open(meta_path, "r") as f: meta = json.load(f)
            safe_name = meta["safe_name"]
            final_dest = os.path.join(self.courses_dir, safe_name)
            
            if os.path.exists(final_dest):
                shutil.rmtree(temp_dir)
                return False, f"Course '{meta['name']}' already exists in your library."
                
            shutil.move(temp_dir, final_dest)
            return True, meta['name']
        except Exception as e:
            if os.path.exists(temp_dir): shutil.rmtree(temp_dir)
            return False, str(e)