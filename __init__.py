from distutils.core import setup
import py2exe
import os
import sys
import shutil
import subprocess

INNO_TEMPLATE = """
[Setup]
AppName=%(app_exe)s
AppVerName=%(app_name)s %(app_ver)s
AppPublisher=%(app_author)s
AppPublisherURL=%(app_www)s
DefaultDirName={pf}\%(app_exe)s
DefaultGroupName=%(app_name)s
DisableProgramGroupPage=true
OutputBaseFilename=setup
Compression=lzma
SolidCompression=true
AllowUNCPath=false
VersionInfoVersion=%(app_ver)s
VersionInfoCompany=%(app_author)s
VersionInfoDescription=%(app_exe)s

[Dirs]
Name: {app}; Flags: uninsalwaysuninstall;

[Files]
Source: dist\*; DestDir: {app}; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: {group}\%(app_name)s; Filename: {app}\\bin\%(app_exe)s.exe; WorkingDir: {app}

[Run]
Filename: {app}\\bin\%(app_exe)s.exe; Description: {cm:LaunchProgram,%(app_exe)s}; Flags: nowait postinstall skipifsilent
"""

GTKRC_TEMPLATE = """
gtk-theme-name = "MS-Windows"
gtk-icon-theme-name = "hicolor"
gtk-fallback-icon-theme = "hicolor"
gtk-alternative-button-order = 1
gtk-alternative-sort-arrows = 1
gtk-auto-mnemonics = 1
gtk-show-input-method-menu = 0
gtk-show-unicode-menu = 0
"""

#http://www.no-ack.org/2010/09/complete-guide-to-py2exe-for-pygtk.html
MSVCR9_TEMPLATE = """
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<assembly xmlns="urn:schemas-microsoft-com:asm.v1" manifestVersion="1.0">
    <noInheritable/>
    <assemblyIdentity
        type="win32"
        name="Microsoft.VC90.CRT"
        version="9.0.21022.8"
        processorArchitecture="x86"
        publicKeyToken="1fc8b3b9a1e18e3b"
    />
    <file name="msvcr90.dll" />
</assembly
"""
MSVCR9_DIRNAME = "Microsoft.VC90.CRT"

class Deploy:

    app_exe = None
    app_name = None
    app_version = None
    app_description = None
    app_author = ""
    app_website = ""
    
    py2exe_windows_options = None
    py2exe_options = None
    distutils_options = {}
    
    curr_dir = None
    root_dir = None
    
    def __init__(self, gtk_path=None, msvcr9_path=None):
        if not gtk_path:
            for libdir in os.environ['PATH'].split(os.path.pathsep):
                if os.path.exists(os.path.join(libdir, 'libgtk-win32-2.0-0.dll')):
                    #strip of ./bin/ to recover the gtk prefix
                    gtk_path = os.path.abspath(os.path.join(libdir,'..'))

        self.gtk_dir = gtk_path
        print "GTK Dir: %s" % self.gtk_dir
        self.msvcr9_path = msvcr9_path
        
        self.check_current_dir()
        self.set_path_variables()
        self.create_deployment_folder()
        self.set_path()
        self.check_dependencies()
        self.deploy_application()
        self.deploy_gtk()
        self.deploy_gtk_theme()
        self.deploy_runtime()
        self.set_py2exe_options()
        self.run_py2exe()
        self.generate_innosetup()
        self.run_innosetup()
        self.close()
        
    def generate_innosetup(self):
        s = INNO_TEMPLATE % {
                "app_exe":self.app_exe,
                "app_name":self.app_name,
                "app_author":self.app_author,
                "app_ver":self.app_version,
                "app_www":self.app_website,
                "dist_dir":self.dist_dir}
        iss = open(os.path.join(self.root_dir,"win32","%s.iss" % self.app_exe), 'w')
        iss.write(s)
        iss.close()
        
    def run_innosetup(self):
        isc = os.path.join("C:\\","Program Files","Inno Setup 5", "ISCC.exe")
        iss = os.path.join(self.root_dir,"win32","%s.iss" % self.app_exe)
        if os.path.exists(isc) and os.path.exists(iss):
            rel = os.path.relpath(self.dist_dir)
            subprocess.call([isc,  "/Oc:%s" % rel, iss])
        
    def check_current_dir(self):
        """
        Derived objects must set and check self.curr_dir and
        self.root_dir if they wish to chain to this function
        """
        raise NotImplementedError
        
    def deploy_application(self):
        """
        Copy application specific files to deployment dirs
        """
        raise NotImplementedError
        
    def set_py2exe_options(self):
        raise NotImplementedError
        
    def check_dependencies(self):
        """
        Check application dependencies
        """
        raise NotImplementedError
        
    def close(self, message=None):
        if message is not None:
            print 'ERROR: %s' % message
            exit(1)
        else:
            exit(0)

    def set_path_variables(self):
        """
        Sets up dir paths for a unix like environment, like
        self.dist._{bin/share/lib/etc}
        """
        assert(self.curr_dir)
        assert(self.root_dir)
        assert(self.app_exe)
        self.dist_dir = os.path.join (self.root_dir, 'win32', 'dist')
        self.dist_bin_dir = os.path.join (self.dist_dir, 'bin')
        self.dist_etc_dir = os.path.join (self.dist_dir, 'etc')
        self.dist_etc_app_dir = os.path.join (self.dist_dir, 'etc', self.app_exe)
        self.dist_share_dir = os.path.join (self.dist_dir, 'share')
        self.dist_share_app_dir = os.path.join (self.dist_share_dir, self.app_exe)
        self.dist_lib_dir = os.path.join (self.dist_dir, 'lib')
        self.dist_lib_app_dir = os.path.join (self.dist_lib_dir, self.app_exe)


    def set_path(self):
        # Add root folder to the python path
        sys.path.insert(0, self.root_dir)
        # Add Gtk to the system path
        for folder in [self.gtk_dir]:
            os.environ['PATH'] = os.environ['PATH']+';'+os.path.join(folder, 'bin')
        os.environ['PATH'] = os.environ['PATH']+';'+self.dist_bin_dir
        
    def create_deployment_folder(self):
        # Create a Unix-like diretory tree to deploy
        print ('Create deployment directory')
        if os.path.exists(self.dist_dir):
            try:
                shutil.rmtree(self.dist_dir)
            except :
                self.close("Can't delete folder %s"%self.dist_dir)

        for path in [self.dist_dir, self.dist_bin_dir, self.dist_etc_dir, self.dist_etc_app_dir,
                self.dist_share_dir, self.dist_lib_app_dir, 
                self.dist_share_app_dir]:
                    if not os.path.exists(path):
                        os.makedirs(path)

    def deploy_gtk(self):
        print ('Deploying Gtk dependencies')
        # Copy Gtk files to the dist folder
        for name in ['fonts', 'pango', 'gtk-2.0']:
            shutil.copytree(os.path.join(self.gtk_dir, 'etc', name),
                    os.path.join(self.dist_etc_dir, name))
        shutil.copytree(os.path.join(self.gtk_dir, 'lib', 'gtk-2.0'),
                os.path.join(self.dist_lib_dir, name))

    def deploy_gtk_theme(self):
        print ('Deploying Gtk theme')
        for name in [os.path.join('icons', 'hicolor'), os.path.join('themes', 'MS-Windows')]:
            shutil.copytree(os.path.join(self.gtk_dir, 'share', name),
                    os.path.join(self.dist_share_dir, name))

        gtkrc = open(os.path.join(self.dist_etc_dir, 'gtk-2.0', 'gtkrc'), 'w')
        gtkrc.write(GTKRC_TEMPLATE)
        gtkrc.close()

    def deploy_runtime(self):
        if self.msvcr9_path and os.path.exists(self.msvcr9_path):
            print ('Deploying %s runtime' % MSVCR9_DIRNAME)
            rtdir = os.path.join(self.dist_bin_dir, MSVCR9_DIRNAME)
            os.makedirs(rtdir)
            manifest = open(os.path.join(rtdir, "%s.manifest" % MSVCR9_DIRNAME), 'w')
            manifest.write(MSVCR9_TEMPLATE)
            manifest.close()
            shutil.copy(self.msvcr9_path,os.path.join(rtdir, "msvcr90.dll"))

    def run_py2exe(self):
        assert(self.app_name)
        assert(self.app_version)
        assert(self.app_description)
        assert(self.py2exe_windows_options != None)
        assert(self.py2exe_options != None)
        
        sys.argv.insert(1, 'py2exe')
        setup(
            name = self.app_name,
            description = self.app_description,
            version = self.app_version,
            windows = [ self.py2exe_windows_options ],
            options = self.py2exe_options,
            zipfile = None,
            **self.distutils_options
        )

