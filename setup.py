# Install with python setup.py install

from distutils.command.install import install
from distutils.core import setup
from os import path
from urllib import request
import os
import shutil
import subprocess
import tarfile
import tempfile


class Install(install):
    def run(self):
        orig_cwd = os.getcwd()

        # Install zint
        try:
            temp_dir = tempfile.mkdtemp()
            print(temp_dir)
            with request.urlopen('https://downloads.sourceforge.net/project/zint/zint/2.6.3/zint-2.6.3.src.tar.gz') as resp:
                with tarfile.open(fileobj=resp, mode='r:gz') as tar:
                    tar.extractall(path=temp_dir)
            build_dir = path.join(temp_dir, os.listdir(temp_dir)[0], 'build')
            os.makedirs(build_dir, exist_ok=True)
            os.chdir(build_dir)
            subprocess.check_call(('cmake', '..'))
            subprocess.check_call(('make',))
            subprocess.check_call(('make', 'install/local')) # Need to specify install path here

            # TODO: Figure out how to solve the dyld errors
            #
            # dyld: Library not loaded: /private/var/folders/f1/mfv95cpj0vgg2rm80ycr846w0000gm/T/tmpf32a0pl7/zint-2.6.3.src/build/backend/libzint.2.6.dylib
            # Referenced from: /Users/mgbelisle/.local/share/virtualenvs/barcode-wheel-8IXH-5lV/bin/zint
            # Reason: image not found
            # [1]    54367 abort      zint --help
            if not os.path.isdir(self.install_scripts):
                os.makedirs(self.install_scripts)
            src = path.join('frontend', 'zint')
            dest = path.join(self.install_scripts, 'zint')
            if path.isfile(dest):
                os.remove(dest)
            self.move_file(src, dest)
            shutil.rmtree(temp_dir)
        finally:
            os.chdir(orig_cwd)

        super().run()
        
setup(
    name='barcode-wheel',
    version='0.0.1',
    author='Matt Willcockson',
    cmdclass={
        'install': Install,
    }
)
