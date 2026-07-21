---
seo:
  title: Hello from Gefyra | Blazingly-fast rocket, rock-solid, local application development arrow_right with Kubernetes.
  description: Gefyra enables blazingly-fast, reliable local application development with Kubernetes. Streamline your workflow, boost productivity, and build with confidence using Gefyra’s powerful development tools.
---

::u-page-hero
---
links:
  - label: Get Started
    to: /en/quick-start/installation
    color: primary
    size: xl
    trailing-icon: i-lucide-arrow-right
  - label: Install Docker Extension
    to: /en/quick-start/installation#docker-desktop-extension
    color: neutral
    size: xl
    trailing-icon: simple-icons-docker
---
#headline
:icon{name="i-gefyra-logo-vertical" mode="svg" class="home-icon"}

#title
Blazingly-fast, rock-solid, local application development with Kubernetes.

#description
Run local code in any Kubernetes cluster without the build and push cycle. It overlays containers in the cluster making code changes immediately available. It's a new era of software development.

#default
  :::card-group
    ::::card
    ---
    title: The Problem
    ---
    Building and pushing containers to test them in Kubernetes is repetitive and time-consuming. Every minor code change forces developers into a slow feedback loop:<br /><br /> <b>Commit -> Build -> Push -> Deploy -> Wait -> Test</b>.<br /><br /> This setup burns expensive CI/CD pipeline resources, slows down engineering velocity, and frustrates development teams.
    ::::

    ::::card
    ---
    title: The Solution
    ---
    Gefyra runs your local code directly in any Kubernetes cluster instantly. By creating a secure, wireguard-encrypted bridge, Gefyra overlays the existing container in Kubernetes with your local environment. <b>You save your file, and the effects are immediately live in the cluster context.</b> No cloud waste, no pipeline waiting times, just pure development speed.
    ::::
  :::
::

::u-page-section
---
class: "border-t"
---
#title
Why Gefyra?

#description
A non-invasive, open-source approach engineered for secure enterprise environments and agile teams.

#features
  :::u-page-feature
  ---
  icon: i-gefyra-deadline
  ---
  #title
  Supercharge Development Speed

  #description
  Zero-Build Live Development. Gefyra temporarily intercepts cluster pods and transparently routes the traffic to your local container runtime. This cuts down feedback loops by 90% and allows engineers to spot and fix environment bugs in seconds.
  :::

  :::u-page-feature
  ---
  icon: i-gefyra-sweat
  ---
  #title
  Native Podman & Docker Support

  #description
  Daemonless Container Engine Compatibility. Gefyra runs flawlessly on Docker Desktop, Rancher Desktop, and native **Podman** environments. It seamlessly aligns with strict corporate security policies by allowing developers to work rootless under Linux.
  :::

  :::u-page-feature
  ---
  icon: i-gefyra-team
  ---
  #title
  User-Specific Bridges

  #description
  Isolated Multi-User Operations. The completely rewritten cluster operator architecture supports dedicated, user-specific network intercepts. **Multiple developers can safely test and debug inside the exact same shared cluster simultaneously** without network conflicts or disturbing each other.
  :::

  :::u-page-feature
  ---
  icon: i-gefyra-play-button
  ---
  #title
  Secure Namespace & RBAC Isolation

  #description
  Granular Kubernetes Enclosure. Gefyra restricts all local connections tightly within the developer's pre-assigned Kubernetes namespaces. Platform teams can confidently greenlight the tool because it fully respects existing RBAC policies without requiring global cluster-admin rights.
  :::

  :::u-page-feature
  ---
  icon: i-gefyra-link
  ---
  #title
  Fight Environment Bugs

  #description
  Shared Kubernetes-based Resources. Your local code execution interacts natively with internal cluster databases, private APIs, and cloud microservices. This eliminates the need for fragile local mocks and guarantees testing under real production-like dependencies from day one.
  :::

  :::u-page-feature
  ---
  icon: i-gefyra-budget
  ---
  #title
  Flexible Workflows

  #description
  Direct IDE & Debugger Integration. Connect live remote cluster traffic seamlessly to local breakpoints in VS Code, IntelliJ, or PyCharm. Developers can diagnose heavy cloud bugs using the powerful, familiar desktop tools they love instead of digging through chaotic log files.
  :::

#footer
:gefyra-marquee
::

:gefyra-use-cases

::u-page-section
---
class: "border-t"
---
#title
How it works

#description
Gefyra acts as a lightweight user-space application and requires **zero permanent modifications** to your production Kubernetes manifests.

  :::u-stepper
  ---
  defaultValue: 2
  disabled: true
  size: lg
  items:
    - title: gefyra up
      description: Prepares your local engine environment and establishes a secure, encrypted Wireguard tunnel directly to your target cluster.
    - title: gefyra bridge
      description: The Gefyra operator hooks into the selected pod/container and transparently intercepts the traffic, tunneling it straight onto your local machine.
    - title: gefyra down
      description: Clean exit. Once you stop your session, Gefyra completely unbridges the components and removes all cluster-side footprints instantly.
  ---
  :::
::

::u-page-section
---
class: "border-t"
---
#title
Let us know about your experience!

#description
We depend on your feedback - Gefyra's was created out of our own needs and the feedback we received from you, and our community.
We'd appreciate it if you could take 2 minutes of your time to fill out our [feedback form]{.font-bold}.

#links
  :::u-button
  ---
  color: primary
  size: xl
  to: https://forms.gle/AWT9NparpTVk8E978
  target: _blank
  trailing-icon: i-lucide-arrow-right
  ---
  Give feedback
  :::
::
