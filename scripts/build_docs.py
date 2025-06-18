#!/usr/bin/env python3
"""
Documentation aggregation and building script.
Fetches documentation from remote repositories and builds a unified site.
"""

import os
import sys
import shutil
import tempfile
import subprocess
import yaml
import logging
from pathlib import Path
from typing import Dict, List, Any
import git
import re

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class DocumentationBuilder:
    def __init__(self, repos_file: str = "repos.yaml"):
        self.repos_file = repos_file
        self.build_dir = Path("_build")
        self.temp_dir = Path("_temp")
        self.source_dir = Path("_source")
        
        # Create necessary directories
        self.build_dir.mkdir(exist_ok=True)
        self.temp_dir.mkdir(exist_ok=True)
        self.source_dir.mkdir(exist_ok=True)
        
        # Load repository configuration
        with open(repos_file, 'r') as f:
            self.config = yaml.safe_load(f)
            
    def clean_directories(self):
        """Clean build and temporary directories"""
        logger.info("Cleaning directories...")
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)
        if self.build_dir.exists():
            shutil.rmtree(self.build_dir)
        if self.source_dir.exists():
            shutil.rmtree(self.source_dir)
            
        self.temp_dir.mkdir(exist_ok=True)
        self.build_dir.mkdir(exist_ok=True)
        self.source_dir.mkdir(exist_ok=True)
        
    def fetch_repository(self, repo_config: Dict[str, Any]) -> Path:
        """Fetch a repository and return the path to its documentation"""
        repo_name = repo_config['name']
        repo_url = repo_config['url']
        doc_dir = repo_config.get('dir', 'docs')
        
        logger.info(f"Fetching repository: {repo_name}")
        
        # Clone repository to temp directory
        repo_path = self.temp_dir / repo_name
        if repo_path.exists():
            shutil.rmtree(repo_path)
            
        try:
            git.Repo.clone_from(repo_url, repo_path, depth=1)
            logger.info(f"Successfully cloned {repo_name}")
        except Exception as e:
            logger.error(f"Failed to clone {repo_name}: {e}")
            return None
            
        # Return path to documentation directory
        doc_path = repo_path / doc_dir
        if not doc_path.exists():
            logger.warning(f"Documentation directory {doc_dir} not found in {repo_name}")
            return None
            
        return doc_path
        
    def preprocess_file_content(self, content: str) -> str:
        """Remove specific unwanted links from file content."""
        # URL to remove, ensure it's properly escaped for regex if needed,
        # though for a simple string replacement, direct replacement is fine.
        # For more complex patterns, re.sub would be better.
        urls_to_remove = [
            "https://clouddocs.f5.com/training/community/rseries-training/html/".
            "https://clouddocs.f5.com/training/community/velos-training/html/",
        ]
        for url_to_remove in urls_to_remove:
            content = content.replace(url_to_remove, "")
        return content

    def process_sphinx_docs(self, doc_path: Path, repo_name: str) -> Path:
        """Process Sphinx documentation and return processed path"""
        logger.info(f"Processing Sphinx documentation for {repo_name}")
        
        # Create target directory
        target_path = self.source_dir / repo_name
        target_path.mkdir(parents=True, exist_ok=True)
        
        # Copy documentation files
        for item in doc_path.iterdir():
            if item.is_file():
                if item.suffix in ['.rst', '.md']:
                    # Read, preprocess, and write
                    with open(item, 'r', encoding='utf-8', errors='ignore') as f_in:
                        content = f_in.read()
                    processed_content = self.preprocess_file_content(content)
                    with open(target_path / item.name, 'w', encoding='utf-8') as f_out:
                        f_out.write(processed_content)
                elif item.suffix in ['.txt']: # Keep .txt files as is for now
                    shutil.copy2(item, target_path)
            elif item.is_dir() and item.name not in ['_build', '__pycache__']:
                shutil.copytree(item, target_path / item.name, dirs_exist_ok=True)
                
        # Create or modify conf.py to disable themes
        self.create_basic_conf(f"{target_path}/conf.py", repo_name)

        return target_path
           
    def create_basic_conf(self, conf_path: Path, repo_name: str):
        """Create a basic conf.py file"""
        logger.info(f"Creating basic conf.py for {repo_name}")
        
        conf_content = f"""# Configuration file for {repo_name}
project = '{repo_name}'

extensions = [
    'sphinx.ext.autodoc',
    'sphinx.ext.viewcode',
    'sphinx.ext.todo',
]

templates_path = ['_templates']
exclude_patterns = ['_build', 'Thumbs.db', '.DS_Store']

html_theme = 'shibuya'
#html_theme = 'basic'
html_title = project
html_short_title = project
html_show_sourcelink = False
html_show_sphinx = False
html_show_copyright = True

html_static_path = ['_static']
"""
        
        with open(conf_path, 'w') as f:
            f.write(conf_content)
            
    def build_sphinx_docs(self, source_path: Path, repo_name: str) -> bool:
        """Build Sphinx documentation"""
        logger.info(f"Building Sphinx documentation for {repo_name}")
        
        build_path = self.build_dir / "html" / repo_name
        build_path.mkdir(parents=True, exist_ok=True)
        
        try:
            cmd = [
                'sphinx-build',
                '-b', 'html',
                '-E',  # Don't use cached environment
                '-q',  # Quiet mode
                str(source_path),
                str(build_path)
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode != 0:
                logger.error(f"Sphinx build failed for {repo_name}: {result.stderr}")
                return False
                
            logger.info(f"Successfully built documentation for {repo_name}")
            return True
            
        except Exception as e:
            logger.error(f"Error building documentation for {repo_name}: {e}")
            return False
            
    def create_index_page(self):
        """Create main index page for the aggregated documentation"""
        logger.info("Creating main index page")
        
        html_content = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Documentation Hub</title>
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 800px;
            margin: 0 auto;
            padding: 20px;
            background-color: #f5f5f5;
        }
        .container {
            background: white;
            padding: 30px;
            border-radius: 8px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }
        h1 {
            color: #2c3e50;
            border-bottom: 3px solid #3498db;
            padding-bottom: 10px;
        }
        .repo-list {
            list-style: none;
            padding: 0;
        }
        .repo-item {
            margin: 15px 0;
            padding: 15px;
            background: #f8f9fa;
            border-left: 4px solid #3498db;
            border-radius: 4px;
        }
        .repo-item a {
            text-decoration: none;
            color: #2c3e50;
            font-weight: 500;
            font-size: 1.1em;
        }
        .repo-item a:hover {
            color: #3498db;
        }
        .repo-description {
            color: #666;
            margin-top: 5px;
            font-size: 0.9em;
        }
        .footer {
            text-align: center;
            margin-top: 30px;
            padding-top: 20px;
            border-top: 1px solid #ddd;
            color: #666;
            font-size: 0.9em;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>📚 Documentation Hub</h1>
        <p>Welcome to the aggregated documentation site. Choose a documentation set to explore:</p>
        
        <ul class="repo-list">
"""
        
        # Add repository links
        for repo in self.config['repos']:
            repo_name = repo['name']
            repo_type = repo.get('type', 'unknown')
            html_content += f"""
            <li class="repo-item">
                <a href="{repo_name}/index.html">{repo_name}</a>
                <div class="repo-description">Type: {repo_type}</div>
            </li>
"""
        
        html_content += """
        </ul>
        
        <div class="footer">
            <p>Documentation built and deployed automatically via GitHub Actions</p>
            <p>Last updated: """ + f"{subprocess.check_output(['date']).decode().strip()}" + """</p>
        </div>
    </div>
</body>
</html>
"""
        
        index_path = self.build_dir / "html" / "index.html"
        with open(index_path, 'w') as f:
            f.write(html_content)
            
    def build_all(self):
        """Build all documentation"""
        logger.info("Starting documentation build process")
        
        # Clean directories
        self.clean_directories()
        
        success_count = 0
        total_count = len(self.config['repos'])
        
        # Process each repository
        for repo_config in self.config['repos']:
            repo_name = repo_config['name']
            repo_type = repo_config.get('type', 'sphinx')
            
            logger.info(f"Processing {repo_name} ({repo_type})")
            
            # Fetch repository
            doc_path = self.fetch_repository(repo_config)
            if not doc_path:
                logger.error(f"Failed to fetch {repo_name}")
                continue
                
            # Process based on type
            if repo_type == 'sphinx':
                source_path = self.process_sphinx_docs(doc_path, repo_name)
                if self.build_sphinx_docs(source_path, repo_name):
                    success_count += 1
            else:
                logger.warning(f"Unsupported documentation type: {repo_type}")
                
        # Create main index page
        self.create_index_page()
        
        logger.info(f"Build complete: {success_count}/{total_count} repositories processed successfully")
        
        if success_count == 0:
            logger.error("No documentation was built successfully")
            sys.exit(1)

def main():
    """Main entry point"""
    builder = DocumentationBuilder()
    builder.build_all()

if __name__ == "__main__":
    main()
