[Go back to getting started](../Getting_started.md) |
[Course content online](https://www.coursera.org/learn/getting-started-with-git-and-github/home/welcome)
___

- [Git and GitHub Fundamentals](#git-and-github-fundamentals)
  - [Course Introduction](#course-introduction)
  - [Overview of Version Control, Git, and GitHub](#overview-of-version-control-git-and-github)
  - [Introduction to GitHub](#introduction-to-github)
  - [GitHub Repositories](#github-repositories)
  - [GitHub - Getting Started](#github---getting-started)
  - [Module Summary](#module-summary)
- [Using Git Commands and Managing GitHub Projects](#using-git-commands-and-managing-github-projects)
  - [GitHub Branches and Pull Requests](#github-branches-and-pull-requests)
  - [Cloning and Forking GitHub Projects](#cloning-and-forking-github-projects)
  - [Managing GitHub Projects](#managing-github-projects)
  - [Module Summary](#module-summary-1)
  - [Using Git Commands from your Desktop](#using-git-commands-from-your-desktop)
  - [Generate an SSH key](#generate-an-ssh-key)
    - [What is an SSH key?](#what-is-an-ssh-key)
    - [Generating an SSH key](#generating-an-ssh-key)
    - [Adding an SSH key to GitHub](#adding-an-ssh-key-to-github)
- [Final project: Part 1 - GitHub UI](#final-project-part-1---github-ui)
  - [Repository link](#repository-link)
  - [License link](#license-link)
  - [Readme](#readme)
    - [examples](#examples)
  - [Code of conduct](#code-of-conduct)
  - [Contribution guidelines](#contribution-guidelines)
    - [Examples](#examples-1)
  - [Script file](#script-file)
- [Final Project: Part 2 - Git CLI](#final-project-part-2---git-cli)
  - [Repository link](#repository-link-1)
    - [pull request](#pull-request)
- [Certificate](#certificate)

# Git and GitHub Fundamentals

## Course Introduction

W​elcome to this course on Git and GitHub! D​istributed Version Control Systems (DVCS) have become critical tools in software development, and key enablers for social and collaborative coding. They are not only being used by Software Engineers and DevOps professionals but also by many other technology practitioners such as Data Scientists and Data Engineers. However their usage is not limited to coding professions only. They are useful anywhere tracking changes/versions and/or collaboration between multiple users is required. At IBM Skills Network, the course instructors and authors use Git repositories extensively even for developing course content such as lab instructions. You will also find usecases in technical documentation, legal document management, and even collaborative development of recipes, books, etc. While there are many distributed versioning systems, Git is amongst the most popular ones. And GitHub is a highly popular Git-based hosted version control platform, and is seeing incredible growth. When some of the videos for this course were developed couple of years earlier, there were over 100 million GitHub repositories, whereas at the time of writing, January 2022, they have grown to over 200 million repositories. These include both public and private repositories for both open source and closed source projects. The popularity of Git and GitHub make their use an essential skill for coding-related professionals like Software Engineers, Application Developers, Mobile Developers, DevOps & Site Reliability Engineers, Data Scientists, and Data Engineers. W​hen you try to get a software-related job or switch to a different one, employers expect you to provide links to your GitHub profile on your resume. I​n this course you will develop the essential conceptual and hands-on skills to work with Git and GitHub. We will start with an overview of Git and GitHub, followed by creation of a GitHub account and a project repository, adding files to it, and committing your changes using the web interface. Next, you will become familiar with Git workflows involving branches and pull requests (PRs) and merges. You will learn to fork and clone public repositories, use pull and push to synchronize your codebase between local and remote repositories, and practice working with Git commands for use in collaborative development workflows. Y​ou will also complete a project at the end to apply and demonstrate your newly acquired skills. I​f you require any clarifications or help, feel free to post on the course discussion forums to interact with your peers and get assistance from the course team. H​ave fun and best wishes! Y​our course instructors, Rav Ahuja and Upkar Lidder

## Overview of Version Control, Git, and GitHub

(Music) In this video, you’ll get an overview of Git and GitHub, which are popular environments among developers and data scientists for performing version control of source code files and projects and collaborating with others. You can’t talk about Git and GitHub without a basic understanding of what version control is. A version control system allows you to keep track of changes to your documents. This makes it easy for you to recover older versions of your document if you make a mistake, and it makes collaboration with others much easier. Here is an example to illustrate how version control works. Let’s say you’ve got a shopping list and you want your roommates to confirm the things you need and add additional items. Without version control, you’ve got a big mess to clean up before you can go shopping. With version control, you know exactly what you need after everyone has contributed their ideas. Git is free and open source software distributed under the GNU General Public License. Git is a distributed version control system, which means that users anywhere in the world can have a copy of your project on their own computer. When they’ve made changes, they can sync their version to a remote server to share it with you. Git isn’t the only version control system out there, but the distributed aspect is one of the main reasons it’s become one of the most common version control systems available. Version control systems are widely used for things involving code, but you can also version control images, documents, and any number of file types. You can use Git without a web interface by using your command line interface, but GitHub is one of the most popular web-hosted services for Git repositories. Others include GitLab, BitBucket, and Beanstalk. There are a few basic terms that you will need to know before you can get started. The SSH protocol is a method for secure remote login from one computer to another. A repository contains your project folders that are set up for version control. A fork is a copy of a repository. A pull request is the way you request that someone reviews and approves your changes before they become final. A working directory contains the files and subdirectories on your computer that are associated with a Git repository. There are a few basic Git commands that you will always use. When starting out with a new repository, you only need create it once: either locally, and then push to GitHub, or by cloning an existing repository by using the command "git init". "git add" moves changes from the working directory to the staging area. "git status" allows you to see the state of your working directory and the staged snapshot of your changes. "git commit" takes your staged snapshot of changes and commits them to the project. "git reset" undoes changes that you’ve made to the files in your working directory. "git log" enables you to browse previous changes to a project. "git branch" lets you create an isolated environment within your repository to make changes. "git checkout" lets you see and change existing branches. "git merge" lets you put everything back together again. To learn how to use Git effectively and begin collaborating with data scientists around the world, you will need to learn the essential commands. Luckily for us, GitHub has amazing resources available to help you get started. Go to try.github.io to download the cheat sheets and run through the tutorials. In the following modules, we'll give you a crash course on setting up your local environment and getting started on a project. 

## Introduction to GitHub

(Music) Welcome to Introduction to GitHub After watching this video, you will be able to: Describe the purpose of source repositories and explain how GitHub satisfies the needs of a source repository. Linux development in the early 2000’s was managed under a free-to-use system known as BitKeeper. In 2005, BitKeeper changed to a for-fee system which was problematic for Linux developers for many reasons. Linus Torvalds led a team to develop a replacement source-version control system. The project ran in a short a timeframe and the key characteristics were defined by a small group. These include: Strong support for non-linear development. (Linux patches were then arriving at a rate of 6.7 patches per second) Distributed development. Each developer can have a local copy of the full development history. Compatibility with existing systems and protocols. This was necessary to acknowledge the diversity of the Linux community. Efficient handling of large projects. Cryptographic authentication of history. This makes certain that distributed systems all have identical code updates. Pluggable merge strategies. Many pathways of development can lead to complex integration decisions that might require explicit integration strategies. What is special about the Git Repository model? Git is designed as a distributed version-control system. Primarily focused on tracking source code during development. Contains elements to coordinate among programmers, track changes, and support non-linear workflows. Created in 2005 by Linus Torvalds for distribution of Linux kernels. Git is a distributed version-control system that is used to track changes to content. It serves as a central point for collaboration with a particular focus on agile development methodologies. In a central version control system, every developer needs to check out code from the central system and commit back into it. As Git is a distributed version control, each developer has a local copy of the full development history, and changes are copied from one such repository to another. Each developer can act as a hub. When Git is used correctly, there is a main branch that corresponds to the deployable code. Teams can continuously integrate changes that are ready to be released and can simultaneously work on separate branches in between releases. Git also allows centralized administration of tasks with access-level controls for each team. Git can co-exist locally such as through the GitHub Desktop client or it can be used directly through a browser connected to the GitHub web interface. IBM Cloud is based on sound and established open-source tools including Git repositories, often called repos. GitHub is an online hosting service for Git repositories. GitHub hosted by a subsidiary of Microsoft. GitHub offers free, professional and enterprise accounts. As of August 2019, GitHub had over 100M repositories. A Repository is: A data structure for storing documents including application source code. A repository can track and maintain version-control. GitLab is a complete DevOps platform, delivered as a single application. GitLab provides access to Git repositories, controlled by source code management. With GitLab, developers can: Collaborate, reviewing code, making comments and helping to improve each other’s code. Work from their own local copy of the code. Branch and merge code when required. Streamline testing and delivery with Built-in Continuous Integration (CI) and Continuous Delivery (CD). In this video, you learned: GitHub is the online hosting service for Git repositories. Repositories store documents including application source code and enable contributors to track and maintain version-control. What is special about the Git Repository model? Git is designed as a distributed version-control system. Primarily focused on tracking source code during development. Contains elements to coordinate among programmers, track changes, and support non-linear workflows. 

## GitHub Repositories

(Music) Welcome to GitHub Repositories! After watching this video, you will be able to: Explain how to sign up for a GitHub account and describe how to create a repository. Signing up for a free, personal account on GitHub is quick and easy. Start at the GitHub site, https://github.com You’ll need to choose a username, enter your email address and select a password, then click Sign up for GitHub. Next, you’ll have a short test to prove that you’re a person. Click Verify and solve the puzzle presented. When you’re done, click join a free plan and then you’ll be taken to a screen where you can select the type of account – most likely a free, personal account is all that you’ll want. Choose to set up a personal, free account, which is the default. GitHub asks some questions about your work, programming experience and interests. You can skip these if you want. Finally, you’ll have to respond to an email that you receive which proves that you linked to GitHub from an account that you access GitHub provides you with some starting points. You can choose to create a repository or an organization, or you can take the Introduction to GitHub course. Remember, a repository is a data structure for storing documents including application source code which tracks and maintains version-control. An organization is a collection of user accounts that owns repositories. Organizations have one or more owners, who have administrative privileges for the organization. Or you can skip this for now and get straight to work. GitHub provides many resources to help you work effectively. When you have time, read the GitHub guide. The heart of a Git-based project is the repository. This contains all your code and the related artifacts, including things like: A README file to describe the purpose of the project. A license to express the ways in which people can use your code, Etc. You can also make your repository private (only available to people with accounts that have permission to see it) or public (searchable and seen by everyone). When you create your repository, you’ll notice that it has a number of tabs, and is 37 00:02:34,310 --&gt; 00:02:37,069 opened to the Code tab. Code – this is where all the source files reside. Git was initially created as a source code repository and now all sorts of files end up in here. If you created a README and/or license, that’s all that’s here right now. Issues – as you can imagine, you can track and plan with tools such as “Issues” that lists all open items against your project base. Pull Requests – this is part of the mechanism for collaborating with other users. Pull requests define changes that are committed and ready for review before being merged into the main branch. Projects – all the tools for managing, sorting, planning, etc. your various projects. This is the core of the collaborative power of GitHub. Wiki, Security, and Insights – often left for more advanced users, these tools provide a communication base to the external user community. Settings – GitHub allows for a lot of personalization, including changing the name of your repository and controlling access. In this video, you learned: How to create and verify a GitHub account. Repositories are storage structures that can hold Code, track Issues, and enable you to collaborate with others. 

## GitHub - Getting Started

In the previous video, you learned about Git and GitHub. Before you continue with this video, register for a GitHub account and log in. Let’s start by creating a new repository. Click + then click New Repository. To create a new repository, you need to provide these details: give your new repository a name; optionally, add a description of your repository; choose the repository visibility - whether you want it to be public or private; and choose the option to Initialize this repository with readme file. Then click Create Repository. You will now be redirected to the repository you have created. The root folder of your repository is listed by default and it has just one file ReadMe.md. Now, it’s time to edit the readme. You can do this in your browser. Just click the pencil to open the online editor and you can change the text of the readme. To save your changes to the repository, you must commit them. After you have made your changes, scroll down to the Commit changes section. Add a commit message and optionally add a description, then click Commit changes. The "commit changes" is used to save your changes to the repository. Go back to the home screen by clicking the repository name link. Note that the readme file is updated and verify your changes. Let’s learn how to create a new file using the built-in web editor provided by GitHub which runs in the browser. Click Add File, then click Create New File to create the new file. To create a python file called firstpython.py. First, provide the file name. Next, add a comment that describes your code, then add the code. Once finished, commit the change to the repository. You can see that your file is now added to the repository and the repository listing shows when the file was added or changed. When you need to change the file, you can edit it again. Click the file name, and then click the pencil icon, make your edits and commit the changes. You can also upload a file from your local system into the repository. From the home screen of the repository, click Add File and choose the Upload files option. Click Choose Your Files and select the files you want to upload from your local system. The file upload process may take a short time, depending on what you are uploading. Once the files finish uploading, click Commit Changes. The repository now reflects the files that were uploaded. In this video, you learned how to create a repository, edit files, and commit changes using the web interface. 

## Module Summary

**In this module, you learned that:**
- A Distributed Version Control System (DVCS) keeps track of changes to code, regardless of where it is stored. This allows multiple users to work on the same codebase or repository, mirroring the codebase on their own computers if needed, while the distributed version control software helps manage synchronization amongst the various codebase mirrors.
- Repositories are storage structures that:
    - Store the code
    - Track issues and changes
    - Enable you to collaborate with others
- G​it is one of the most popular distributed version control systems. GitHub, GitLab and Bitbucket are examples of hosted version control systems.

# Using Git Commands and Managing GitHub Projects

## GitHub Branches and Pull Requests

(Music) Welcome to GitHub Branches! After watching this video, you will be able to: Explain the purpose of branches and describe how to merge changes into branches. All files in GitHub are stored on a branch. The master branch is definitive. It stores the deployable version of your code. The master branch is created by default, however, you can use any branch as the main, finished, deployable version of the code. When you plan to change things, you create a new branch and give it a descriptive name. The new branch starts as an exact copy of the original branch. As you make changes, the branch that you created holds the changed code. To create a new branch, click drop-down branch: master Add new branch name into new branch text and select Create branch. GitHub branches can be very complex for large software projects. For a simple project, such as the ones we are exploring, consider the following: Start with a common base, the initial source for this project. At one point, the code is branched while new features are developed. In this example, both branches are undergoing changes. When the two streams of work are ready to merge, each branch’s code is identified as a tip. and the two tips are merged into a third, combined branch. Developers work on source files in a branch. Since some projects take a while, the source doesn’t make sense right away. To change the contents of a file: Select the file. Click the pencil icon. Make the changes. Commit the changes. When the developer has completed their assigned work, to save their changes, they commit the code. Commit indicates that the developer is convinced that the code represents a stable platform for the feature or set of features being developed. When a developer commits changed source to their path, they are required to write a comment that describes the changes. The comment should be meaningful and descriptive. The developer can choose to commit to the current branch or create a new branch. Some best practices : Don’t end the commit message with a period. Keep commit messages under 50 characters – use the extended window for the details. Always write in an “active” voice. Pull is used to initiate the merging of branches in a way to capture changes. A pull request makes the proposed (committed) changes available for others to review and use. A pull can follow any commits, even if code is unfinished. A pull requires a user to approve the changes. This can be the author of the change or it can be assigned within the team. Note that GitHub automatically makes a pull request on your behalf if you make a change on a branch that you do not own. Since the log files are immutable, it is always possible to find the person who approved the merge of the change. To open a new pull request: Click Pull request and select New pull request. Select the new branch from the compare box. Scroll down to view the changes. Confirm that the changes are what you want to assess. Add a title and description to the request. Click Create pull request. The intent of Git repositories is for the master branch to be the only deployed code. Developers can change source files in a branch but the changes are not released until. They are committed. A pull command is issued. The code is reviewed and approved. The approved code is merged back into the master code. To merge a committed code change into your master code: Click Merge pull request. Click Confirm merge. When all changes for a branch are complete, that branch is considered obsolete and it should be deleted. In this video, you learned: All files in GitHub exist on a branch. The Master Branch contains the finished, deployable version of the code. Create new branches when you need to change the code. The new branch starts as an exact copy of the original branch. As you make changes, the branch that you created holds the changed code. More than one branch can be undergoing changes at the same time. Saved changes are called commits. Pull requests enables other users to review and use the proposed changes (committed). When you are ready to merge the changed code into the master branch, you merge the committed code changes into your master code. 

## Cloning and Forking GitHub Projects

(Music) Welcome to Cloning and Forking GitHub Projects. After watching this video, you will be able to: Clone and sync repositories. Fork a project to make a base for a new project. Use git commands to communicate with other developers. GitHub has over existing 100M repositories, including some very useful projects. Whether you are joining a team or basing your own project on prior work, some of the most powerful tools are forking and cloning a repository. Cloning generally refers to creating a copy of a repository on your local machine. Cloned copies can be kept in sync between the two locations. Forking allows you to modify or extend a project without affecting the original project. Frequently, this is used to take an existing project and make it the starting point for your new project. To clone a GitHub repository, navigate to the repository that you want to clone. Under the repository name, click Code. In the Clone with HTTPS section, click the clipboard button to copy the URL. To download the source code, you can click Download zip, but without the version control information. On your local machine, open a “Terminal” window and change to the directory where you want the clone to be copied. Type “git clone” followed by pasting the URL that you copied above and then press ENTER to execute the cloning. When you have made your changes and are ready to sync your code back to GitHub. First, you must run the “git add &lt;files&gt;” command. This moves the changed files into a staging area on the GitHub repository. The staging area is an area where commits can be formatted and reviewed before completing the commit. Next, when you are ready, run “git commit –m &lt;message&gt;” and this will commit changes in the staging area. When you are ready to move your changes fully into the GitHub repository. Use the “git push” command. This will push all the committed changes into the repository. Remote repositories are repositories that are stored elsewhere – on the internet, on your network, even on your local computer. You can have several of remote repositories, each of which generally is either read-only or read/write for you. Collaborating with others involves managing these remote repositories and involves push, pull, and fetch operations to and from them when you need to share work. Use git push to transfer your changes to the remote repo. Use git fetch to transfer any changes from the remote repo to your local repo. It does not merge those changes to the branch you are working on. You can perform a merge manually if you want. Use git pull to transfer any changes from the remote repo to your local repo, and merge them to a branch. Developers use the terms upstream and origin when talking about remote reps. Origin generally refers to your fork and upstream refers to the original work. These are the norms. You can of course name them anything you like. Forking is used to take a copy of a GitHub repository and use it as the base for a new project. You can also use forking to submit back changes into the original repository. This is also used to independently make changes to a project. In that instance, when you are satisfied with your changes, submit a pull request to the original project owner. They can decide whether or not to accept your changes. It is often a legal requirement to keep a copy of the of the license file. Even if no legal requirement exists, it’s good practice. Navigate to the repository that you want to fork. In the top-right corner, click the “Fork” button. To keep a fork in sync with the original work from a local clone. First, create a local clone of the project. To configure Git to sync your fork: Open a Terminal and change to the directory containing the clone. Type “git remote –v” This gives you the remote repository. Type “git remote add upstream &lt;PASTE&gt;” with the pasted-in directory that you used in creating your clone. Adding upstream adds the original repository as a new remote repository labelled upstream. If you type “git remote –v”, you’ll see the change reflected. Other commands of interest include “git fetch upstream” to grab upstream branches and “git merge upstream/master” which merges changes into the master branch. You will also see "git pull upstream" used to fetch and merge the remote branch in the same step. “Git pull upstream" reduces the number of steps to sync with a remote branch, but the automatic merges are not always desired. In this video, you learned: GitHub has over existing 100M repositories that you can use. You can clone a repository to copy it to your local machine and sync changes back to the original repository. You can fork a repository to use it as the base for a new project, or to work on a project independently.

## Managing GitHub Projects

(Music) Welcome to Managing GitHub Projects. After watching this video, you will be able to: Understand common roles in a Git project. Use git commands to communicate with other developers. A Developer working as a participant in a group project needs to learn how to communicate with others and uses these commands in addition to the ones needed by a standalone developer. When working with Git, you can use Git commands or a desktop tool such as GitHub Desktop. git-clone from the upstream to prime the local repository. git-pull and git-fetch from "origin" to keep up-to-date with the upstream. git-push to shared repository, if you adopt CVS style shared repository workflow. git-format-patch to prepare e-mail submission, if you adopt Linux kernel-style public forum workflow. git-send-email to send your e-mail submission without corruption by your MUA. git-request-pull to create a summary of changes for your upstream to pull. An integrator in a group project receives changes made by others, reviews and integrates them that is responds to pull requests and publishes the result for others to use. Integrators use the following commands in addition to the ones needed by participants. git-am to apply patches e-mailed in from your contributors. git-pull to merge from your trusted lieutenants. git-format-patch to prepare and send suggested alternative to contributors. git-revert to undo botched commits. git-push to publish the bleeding edge. A Repository Administrator uses the following tools to set up and maintain access to the repository by developers. git-daemon to allow anonymous download from repository. git-shell can be used as a restricted login shell for shared central repository users. git-http-backend provides a server-side implementation of Git-over-HTTP ("Smart http") allowing both fetch and push services. gitweb provides a web front-end to Git repositories, which can be set-up using the git-instaweb script. Repository Admins can use GitHub Actions to automate software workflows, including continuous integration and continuous delivery. In this video, you learned: There are multiple roles involved in managing a project: Developer Integrator and Repository Administrator Each role uses different git commands to communicate with collaborators.

## Module Summary

**In this module, you learned that:**
- Branches are used to isolate changes to code. When the changes are complete, they can be merged back into the main branch.
- Repositories can be cloned to make it possible to work locally, then sync changes back to the original.
- Repositories can be forked to be used as a base for a new project, or so that the developer can work independently.
- A​ Pull Request (PR) can be submitted to have your changes reviewed and merged.
- Large projects include people working in different roles:
    - Developer – creates code
    - Integrator – manages changes made by developers
    - Repository Administrator – configures and maintains access to the repository

## Using Git Commands from your Desktop

I​n the previous lab you used a Cloud-based IDE to work with Git commands. In many cases, you will be developing code on your own workstation on your desktop/laptop. Linux systems typically come pre-installed with Git commands or if needed you can install them using dnf on rpm based distributions (e.g. Red Hat / Fedora): sudo dnf install git-all o​r, apt on Debian-based distributions (e.g. Ubuntu): sudo apt install git-all O​n MacOS you can activate Git by typing: git version H​owever if it is not installed, or if you want to update it, you can download and install the latest version of the MacOS Git Installer, and run the above command to verify the version. O​n Windows based systems, you can install Git Bash by downloading the Git for Windows installer. Git Bash includes popular Linux Bash shell commands (such as ls, pwd, cat, etc.) as well as Git commands. Y​ou can also get the GitHub desktop for Windows and MacOS, which provides a UI for GitHub on your desktop. W​hen you are working with GitHub repositories from your desktop you will also need to setup an ssh key. The remaining labs in this module are optional however recommended for those with a Windows desktop. In the following labs you will install Git Bash on your Windows machine, and configure an ssh key to work with your GitHub repo using Git commands on your system.

## Generate an SSH key

### What is an SSH key?

An SSH key is an access credential in the SSH protocol. Its function is similar to that of user names and passwords, but the keys are primarily used for automated processes.

### Generating an SSH key

**To generate an SSH key, complete the following steps:**

1. Launch a terminal. If you are using Windows, launch Git Bash.
2. Type the following command in your terminal, replacing <your email address> with the email address that is linked to your Github account. When you have typed the command, press Enter.
    ```
    ssh-keygen -t rsa -b 4096 -C "<your email address>"
    ```
    A new SSH key is generated.

3. You will be prompted to enter a directory to save the key. You can simply press Enter to accept the default location, which is an .ssh folder in the home directory. This means you will be able to locate the key in ~/.ssh/id_rsa.
4. You will be prompted to choose a passphrase. You also have the option not to create a passphrase. To skip the passphrase, press Enter twice to confirm that the passphrase is empty.
5. Optional: To navigate to the .ssh directory, and check the contents of the directory, run the following commands in the terminal:
    ```
    cd ~/.ssh
    ls
    ```
    When you list the contents of the .ssh directory, you should see id_rsa and id_rsa.pub in the list of contents, where id_rsa is the private version of your key and id_rsa.pub is the public version of your key.

6. You now need to add the SSH key to the ssh-agent, which helps with the authentication process. To start the ssh-agent, run the following command in the terminal:
    ```
    eval "$(ssh-agent -s)"
    ```
7. To add the key to the agent, run the following command in the terminal:
    ```
    ssh-add ~/.ssh/id_rsa
    ```

### Adding an SSH key to GitHub

To add an SSH key to GitHub, you need to copy the SSH key that you generated in the previous lab. Open a terminal and then complete the following steps:

1. In the terminal, run the following command:
    ```
    cat ~/.ssh/id_rsa.pub | clip
    ```
    **Note**: If clip doesn't work, run cat ~/.ssh/id_rsa.pub in the command line and the copy the output.

2. Sign in to GitHub. At the top right, click the drop-down menu on your profile image and select Settings.
  
    <img src=".//Assets/settings.png">
  
3. From the "Personal settings" menu, select SSH and GPG keys

    <img src=".//Assets/SSHKey_option_new.png">

4. Click New SSH key.

    <img src=".//Assets/AddNewSSH.png">

5. Enter a title for the new SSH key. In the Key field, paste the key that you copied in step 1, above. The pasted key should include Your email address at the end

    <img src=".//Assets/add_ssh_keytoaccount_new.png">

6. Click Add SSH Key. The SSH key is added to your account.

# Final project: Part 1 - GitHub UI

## Repository link
https://github.com/jfar/github-final-project.git

## License link
https://github.com/jfar/github-final-project/blob/main/LICENSE

## Readme
https://github.com/jfar/github-final-project/blob/main/README.md

### examples
- [Github README](https://docs.github.com/en/github/creating-cloning-and-archiving-repositories/about-readmes)
- [Make a README](https://makeareadme.com/?utm_medium=Exinfluencer&utm_source=Exinfluencer&utm_content=000026UJ&utm_term=10006555&utm_id=NA-SkillsNetwork-Channel-SkillsNetworkCoursesIBMCD0131ENSkillsNetwork32121029-2022-01-01)
- [Awesome README](https://github.com/matiassingers/awesome-readme)

## Code of conduct
https://github.com/jfar/github-final-project/blob/main/CODE_OF_CONDUCT.md

## Contribution guidelines
https://github.com/jfar/github-final-project/blob/main/CONTRIBUTING.md

### Examples
- [Contributing to Legit Info, a Call for Code for Racial Justice Project](https://github.com/Call-for-Code-for-Racial-Justice/Legit-Info/blob/main/CONTRIBUTING.md)
- [Contributing to OpenEEW](https://github.com/openeew/openeew/blob/master/CONTRIBUTING.md)
- [Contributing to Atom](https://cf-courses-data.s3.us.cloud-object-storage.appdomain.cloud/IBM-CD0131EN-SkillsNetwork/labs/project/github.com/atom/atom/blob/master/CONTRIBUTING.md%E2%80%8B)
- [How to contribute to Ruby on Rails](https://cf-courses-data.s3.us.cloud-object-storage.appdomain.cloud/IBM-CD0131EN-SkillsNetwork/labs/project/github.com/rails/rails/blob/main/CONTRIBUTING.md%E2%80%8B)

## Script file
https://github.com/jfar/github-final-project/blob/main/simple-interest.sh

# Final Project: Part 2 - Git CLI

## Repository link
https://github.com/jfar/jbbmo-Introduction-to-Git-and-GitHub

### pull request
https://github.com/ibm-developer-skills-network/jbbmo-Introduction-to-Git-and-GitHub/pull/4411

https://github.com/ibm-developer-skills-network/jbbmo-Introduction-to-Git-and-GitHub/pull/4412

# Certificate

- [Click here](./Assets/Coursera%20LADH4KMTAZCK.pdf) to view and download the course certificate