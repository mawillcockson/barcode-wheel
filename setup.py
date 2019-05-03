# Install with python setup.py install

from distutils.command.install import install
from distutils.core import setup
from os import path
from urllib import request
import io
import os
import shutil
import subprocess
import tarfile
import tempfile


class Install(install):
    def run(self):
        # Install zint
        temp_dir = tempfile.mkdtemp()
        with request.urlopen('https://downloads.sourceforge.net/project/zint/zint/2.6.3/zint-2.6.3.src.tar.gz') as resp:
            with tarfile.open(fileobj=resp, mode='r:gz') as tar:
                tar.extractall(path=temp_dir)
        build_dir = path.join(temp_dir, os.listdir(temp_dir)[0])
        install_dir = path.join(self.install_base, 'zint')
        shutil.rmtree(install_dir, ignore_errors=True)
        os.makedirs(install_dir)
        subprocess.check_call(('cmake', '-B', install_dir, build_dir))
        subprocess.check_call(('make', '-C', install_dir))
        subprocess.check_call(('make', '-C', install_dir, 'install/local'))
        os.makedirs(self.install_scripts, exist_ok=True)
        src = path.join(install_dir, 'frontend', 'zint')
        dest = path.join(self.install_scripts, 'zint')
        if path.isfile(dest):
            os.remove(dest)
        os.symlink(src, dest)
        shutil.rmtree(temp_dir)

        # Install harfbuzz
        temp_dir = tempfile.mkdtemp()
        with request.urlopen('https://www.freedesktop.org/software/harfbuzz/release/harfbuzz-2.4.0.tar.bz2') as resp:
            # BytesIO is needed because bz2 does a seek()
            with tarfile.open(fileobj=io.BytesIO(resp.read()), mode='r:bz2') as tar:
                tar.extractall(path=temp_dir)
        build_dir = path.join(temp_dir, os.listdir(temp_dir)[0])
        install_dir = path.join(self.install_base, 'harfbuzz')
        shutil.rmtree(install_dir, ignore_errors=True)
        os.makedirs(install_dir)
        orig_cwd = os.getcwd()
        os.chdir(build_dir)
        subprocess.check_call((
            path.join(build_dir, 'configure'),
            '--with-gobject',
            '--enable-introspection',
            '--prefix', install_dir,
        ))
        subprocess.check_call(('make',))
        subprocess.check_call(('make', 'install'))
        os.chdir(orig_cwd)
        # TODO: Something else needed here probably
        shutil.rmtree(temp_dir)        
        
        super().run()
        
setup(
    name='barcode-wheel',
    version='0.0.1',
    author='Matt Willcockson',
    cmdclass={
        'install': Install,
    }
)
