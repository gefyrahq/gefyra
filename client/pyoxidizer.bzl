# This file defines how PyOxidizer application building and packaging is
# performed. See PyOxidizer's documentation at
# https://pyoxidizer.readthedocs.io/en/stable/ for details of this
# configuration file format.

def resource_callback(policy, resource):
    if type(resource) in ("File"):
        if "pywin" in resource.path or "pypiwin" in resource.path:
            resource.add_location = "filesystem-relative:lib"
            resource.add_include = True
    if type(resource) in ("PythonExtensionModule"):
        if resource.name in ["_ssl", "win32.win32file", "win32.win32pipe"]:
            resource.add_location = "filesystem-relative:lib"
            resource.add_include = True
    elif type(resource) in ("PythonModuleSource", "PythonPackageResource", "PythonPackageDistributionResource"):
        if resource.name in ["pywin32_bootstrap", "pythoncom", "pypiwin32", "pywin32", "pythonwin", "win32", "win32com", "win32comext", "git+https://github.com/gefyrahq/grapheme"]:
            resource.add_location = "filesystem-relative:lib"
            resource.add_include = True

def make_exe():
    dist = default_python_distribution()
    policy = dist.make_python_packaging_policy()
    policy.allow_in_memory_shared_library_loading = True
    policy.bytecode_optimize_level_one = True
    policy.include_non_distribution_sources = False
    policy.include_test = False
    policy.resources_location = "in-memory"
    policy.resources_location_fallback = "filesystem-relative:prefix"
    python_config = dist.make_python_interpreter_config()

    python_config.run_command = "from gefyra.cli.main import main; main()"

    exe = dist.to_python_executable(
        name="gefyra",
        packaging_policy=policy,
        config=python_config,
    )

    # linux, mac
    exe.add_python_resources(exe.read_package_root(CWD, ["gefyra"]))
    exe.add_python_resources(exe.pip_install(["--no-deps", "docker==6.0.1"]))
    # certifi from version 2022.06.15.1 does not work
    exe.add_python_resources(exe.pip_install(["chardet", "certifi==2022.06.15", "kubernetes", "packaging==21.3", "tabulate", "cli-tracker", "prompt_toolkit", "alive-progress", "git+https://github.com/gefyrahq/grapheme", "click"]))
    return exe

def make_win_exe():
    dist = default_python_distribution()
    policy = dist.make_python_packaging_policy()

    policy.allow_in_memory_shared_library_loading = True

    policy.bytecode_optimize_level_one = True
    policy.extension_module_filter = "all"
    policy.include_file_resources = True

    policy.include_test = False
    policy.resources_location = "in-memory"
    policy.resources_location_fallback = "filesystem-relative:lib"
    policy.allow_files = True
    policy.file_scanner_emit_files = True
    policy.register_resource_callback(resource_callback)
    python_config = dist.make_python_interpreter_config()
    python_config.module_search_paths = ["$ORIGIN", "$ORIGIN/lib"]

    python_config.run_command = "from gefyra.cli.main import main; main()"

    exe = dist.to_python_executable(
        name="gefyra",
        packaging_policy=policy,
        config=python_config,
    )

    # windows
    exe.add_python_resources(exe.read_package_root(CWD, ["gefyra"]))
    exe.add_python_resources(exe.pip_install(["--no-deps", "docker==6.0.1"]))
    # certifi from version 2022.06.15.1 does not work
    exe.add_python_resources(exe.pip_install(["chardet", "certifi==2022.06.15", "pywin32", "kubernetes", "packaging==21.3", "tabulate", "cli-tracker", "prompt_toolkit", "alive-progress", "grapheme", "click"]))
    exe.windows_runtime_dlls_mode = "always"
    return exe

def make_embedded_resources(exe):
    return exe.to_embedded_resources()

def make_install(exe):
    # Create an object that represents our installed application file layout.
    files = FileManifest()

    # Add the generated executable to our install layout in the root directory.
    files.add_python_resource(".", exe)

    return files

def make_msi(exe):
    # See the full docs for more. But this will convert your Python executable
    # into a `WiXMSIBuilder` Starlark type, which will be converted to a Windows
    # .msi installer when it is built.
    return exe.to_wix_msi_builder(
        # Simple identifier of your app.
        "myapp",
        # The name of your application.
        "My Application",
        # The version of your application.
        "1.0",
        # The author/manufacturer of your application.
        "Alice Jones"
    )


# Tell PyOxidizer about the build targets defined above.
register_target("exe", make_exe)
register_target("winexe", make_win_exe)
register_target("resources", make_embedded_resources, depends=["exe"], default_build_script=True)
register_target("wininstall", make_install, depends=["winexe"], default=True)
register_target("msi_installer", make_msi, depends=["winexe"])

# Resolve whatever targets the invoker of this configuration file is requesting
# be resolved.
resolve_targets()
