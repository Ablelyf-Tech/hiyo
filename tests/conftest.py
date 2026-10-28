import subprocess
from pathlib import Path
import pytest
from engineering_os.store import Store

@pytest.fixture
def store(tmp_path):
    return Store(tmp_path / 'state')

@pytest.fixture
def workspace(tmp_path):
    path = tmp_path / 'projects' / 'sample'
    path.mkdir(parents=True)
    for args in [['init'],['config','user.email','test@example.invalid'],['config','user.name','Test Engineer']]:
        subprocess.run(['git',*args],cwd=path,check=True,capture_output=True)
    (path / 'README.md').write_text('# Sample\n')
    subprocess.run(['git','add','.'],cwd=path,check=True)
    subprocess.run(['git','commit','-m','initial'],cwd=path,check=True,capture_output=True)
    return path
