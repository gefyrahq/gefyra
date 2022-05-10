# This file defines how PyOxidizer application building and packaging is
# performed. See PyOxidizer's documentation at
# https://pyoxidizer.readthedocs.io/en/stable/ for details of this
# configuration file format.

def make_exe():
    # Obtain the default PythonDistribution for our build target. We link
    # this distribution into our produced executable and extract the Python
    # standard library from it.
    dist = default_python_distribution()

    # This function creates a `PythonPackagingPolicy` instance, which
    # influences how executables are built and how resources are added to
    # the executable. You can customize the default behavior by assigning
    # to attributes and calling functions.
    policy = dist.make_python_packaging_policy()

    # Enable support for non-classified "file" resources to be added to
    # resource collections.
    # policy.allow_files = True

    # Control support for loading Python extensions and other shared libraries
    # from memory. This is only supported on Windows and is ignored on other
    # platforms.
    policy.allow_in_memory_shared_library_loading = True

    # Control whether to generate Python bytecode at various optimization
    # levels. The default optimization level used by Python is 0.
    # policy.bytecode_optimize_level_zero = True
    # policy.bytecode_optimize_level_one = True
    policy.bytecode_optimize_level_two = True

    # Package all available Python extensions in the distribution.
    policy.extension_module_filter = "all"

    # Package the minimum set of Python extensions in the distribution needed
    # to run a Python interpreter. Various functionality from the Python
    # standard library won't work with this setting! But it can be used to
    # reduce the size of generated executables by omitting unused extensions.
    # policy.extension_module_filter = "no-copyleft"

    # Package Python extensions in the distribution not having additional
    # library dependencies. This will exclude working support for SSL,
    # compression formats, and other functionality.
    # policy.extension_module_filter = "all"

    # Controls whether `File` instances are emitted by the file scanner.
    # policy.file_scanner_emit_files = False

    # Controls the `add_include` attribute of "classified" resources
    # (`PythonModuleSource`, `PythonPackageResource`, etc).
    # policy.include_classified_resources = True

    # Toggle whether Python module source code for modules in the Python
    # distribution's standard library are included.
    # policy.include_distribution_sources = False

    # Toggle whether Python package resource files for the Python standard
    # library are included.
    # policy.include_distribution_resources = False

    # Controls the `add_include` attribute of `File` resources.
    # policy.include_file_resources = False

    # Controls the `add_include` attribute of `PythonModuleSource` not in
    # the standard library.
    policy.include_non_distribution_sources = False

    # Toggle whether files associated with tests are included.
    policy.include_test = False

    # Use in-memory location for adding resources by default.
    policy.resources_location = "in-memory"

    # Attempt to add resources relative to the built binary when
    # `resources_location` fails.
    policy.resources_location_fallback = "filesystem-relative:prefix"

    # The configuration of the embedded Python interpreter can be modified
    # by setting attributes on the instance. Some of these are
    # documented below.
    python_config = dist.make_python_interpreter_config()

    # Evaluate a string as Python code when the interpreter starts.
    python_config.run_command = "from gefyra.__main__ import main; main()"

    # Produce a PythonExecutable from a Python distribution, embedded
    # resources, and other options. The returned object represents the
    # standalone executable that will be built.
    exe = dist.to_python_executable(
        name="gefyra",

        # If no argument passed, the default `PythonPackagingPolicy` for the
        # distribution is used.
        packaging_policy=policy,

        # If no argument passed, the default `PythonInterpreterConfig` is used.
        config=python_config,
    )

    # Invoke `pip install` using a requirements file and add the collected resources
    # to our binary.
    exe.add_python_resources(exe.pip_install(["docker==5.0.3", "kubernetes==19.15.0"]))

    # Install Windows runtime DLLs.
    exe.windows_runtime_dlls_mode = "always"
    exe.windows_subsystem = "console"

    # Read Python files from a local directory and add them to our embedded
    # context, taking just the resources belonging to the `foo` and `bar`
    # Python packages.
    exe.add_python_resources(exe.read_package_root(
        path=".",
        packages=["gefyra"],
    ))

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


# Dynamically enable automatic code signing.
def register_code_signers():
    # You will need to run with `pyoxidizer build --var ENABLE_CODE_SIGNING 1` for
    # this if block to be evaluated.
    if not VARS.get("ENABLE_CODE_SIGNING"):
        return

    # Use a code signing certificate in a .pfx/.p12 file, prompting the
    # user for its path and password to open.
    # pfx_path = prompt_input("path to code signing certificate file")
    # pfx_password = prompt_password(
    #     "password for code signing certificate file",
    #     confirm = True
    # )
    # signer = code_signer_from_pfx_file(pfx_path, pfx_password)

    # Use a code signing certificate in the Windows certificate store, specified
    # by its SHA-1 thumbprint. (This allows you to use YubiKeys and other
    # hardware tokens if they speak to the Windows certificate APIs.)
    # sha1_thumbprint = prompt_input(
    #     "SHA-1 thumbprint of code signing certificate in Windows store"
    # )
    # signer = code_signer_from_windows_store_sha1_thumbprint(sha1_thumbprint)

    # Choose a code signing certificate automatically from the Windows
    # certificate store.
    # signer = code_signer_from_windows_store_auto()

    # Activate your signer so it gets called automatically.
    # signer.activate()


# Call our function to set up automatic code signers.
register_code_signers()

# Tell PyOxidizer about the build targets defined above.
register_target("exe", make_exe)
register_target("resources", make_embedded_resources, depends=["exe"], default_build_script=True)
register_target("install", make_install, depends=["exe"], default=True)
register_target("msi_installer", make_msi, depends=["exe"])

# Resolve whatever targets the invoker of this configuration file is requesting
# be resolved.
resolve_targets()
