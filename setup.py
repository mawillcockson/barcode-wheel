# This runs appropriately with `pip install .` but not with `pipenv install -e .` and not sure why.

from distutils.command.build import build
from distutils.core import setup


class Build(build):
    '''
    Custom build script
    '''
    def run(self):
        if True:
            exit('Custom error')
        super().run()
        
setup(
    name='barcode-wheel',
    version='0.0.1',
    author='Matt Willcockson',
    cmdclass={
        'build': Build,
    }
)
