# Install with python setup.py install

from distutils.command.build import build
from distutils.core import setup
from os import path
from urllib import request
import os
import shutil
import subprocess
import tarfile
import tempfile


class Build(build):
    def run(self):
        temp_dir = tempfile.mkdtemp()
        print(temp_dir)
        owd = os.getcwd()
        try:
            # Build zint
            with request.urlopen('https://downloads.sourceforge.net/project/zint/zint/2.6.3/zint-2.6.3.src.tar.gz') as resp:
                with tarfile.open(fileobj=resp, mode='r:gz') as tar:
                    tar.extractall(path=temp_dir)
            build_dir = path.join(temp_dir, os.listdir(temp_dir)[0], 'build')
            os.makedirs(build_dir, exist_ok=True)
            os.chdir(build_dir)
            subprocess.check_call(('cmake', '..'))
            subprocess.check_call(('make',))
            # TODO: Continue here. Save the binaries so that the install step can place them in the
            # in pipenv binary folder.
            shutil.rmtree(temp_dir)
        finally:
            os.chdir(owd)
        super().run()
        
setup(
    name='barcode-wheel',
    version='0.0.1',
    author='Matt Willcockson',
    cmdclass={
        'build': Build,
    }
)
