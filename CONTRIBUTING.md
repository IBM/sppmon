# Create an GitHub issue
While GitHub does not make issues mandatory, it is a good idea to use them.  It creates a space for discussions, and also provides tracking of all activity surrounding the work.

- Navigate to https://github.com/IBM/spectrum-protect-sppmon/issues/new
- Select an appropriate title
- Enter a description, if applicable.
- Take note of the issue number, it will be used later.

## Requesting / Implementing Features

To request or implement a feature, please open an issue.
This issue should contain:
- Short description of what you're requesting
- What is the goal/intention of the feature request
- How does it benefit working with SPPMon?

We will assign the Label `enhancement` to it, so it is clearly labeled.

## Reporting Bugs

If you've encountered a bug, please check first our [wiki](https://github.com/IBM/spectrum-protect-sppmon/wiki) for a solution or workaround.
Then, open an issue.
This issue should contain:
- The prefix `BUG:` in the title
- A short description of what the bug is
- Steps how to recreate

We will assign the Label `bug` to it, so it is clearly labeled.

# Fork this repository
In GitHub, all work is typically done in a "fork". The fork is a private copy of the main repository. All changes will be published to the main repository once they have been reviewed and accepted by a main repository owner.

- Click on the "Fork" button in the top left area of the page.
- This will create and navigate you to a private copy of this repository (notice the URL is slightly different from the main repository).
- This is where all the work will be done, and reviewed before getting pulled/published to the main repository.

# Create a Pull request
Once you are happy with the of your work and want to publish it, you will need to create a "Pull request". This is where the SPPmon team will have a chance to review the changes before accepting them into the public repository.

- Navigate to your fork.
- Switch to the "Pull requests" tab.
- Click the "New pull request" button.
- Click the "Create pull request" button.
- In the title, reference the issue number, prefixed with a pound sign.
- Optionally add comments.
- Click the "Create pull request".
- We will receive a notification, do the review and eventually accept the pull request into the main repository.

# Coding Standards

Please see the [wiki](https://github.com/IBM/spectrum-protect-sppmon/wiki) for our Coding standards. 
We are using Visual Studio Code, including:
- Pylance 
- Python Docstring
