# Security

## Supported versions

Only the latest release receives fixes. The project is at an early stage and has one maintainer.

## What to report

holon's scripts read and write files on your machine, and `install` can download and unpack a repository or archive from a URL. Please report anything that lets a tree, an archive or a URL make the scripts read or write outside the folders they were pointed at, or run code the user did not ask for.

## How to report

Do not open a public issue for a security problem. Use GitHub's private vulnerability reporting ("Security" tab, "Report a vulnerability") on this repository. Include the command, the input that triggers the problem, and what happened. If you cannot use that form, email Wneil2020@163.com with "holon skill security" in the subject.

You will get a reply when the maintainer has read the report. Fixes are released as soon as they are ready, and the report is credited in the changelog unless you ask otherwise.
