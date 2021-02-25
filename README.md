# roblox-group-scraper
Tool for finding ownerless Roblox groups.

![Screenshot](screenshot.png)


# Config
- `threadCount`: amount of threads to be used for scanning
- `displayErrors`: display errors related to scraping
- `minimumMemberCount`: groups with member counts below this amount won't be shown
- `range`: group ids will count up from `min`, up until `max`

# Output
Matched groups will be logged into the file `found.csv` with the following fields:
- Id
- Member count
- Url
- Name

# Usage
- Download and install the latest python 3 release from https://www.python.org/downloads/ (while installing, check 'Add to PATH')
- Download and extract the tool from https://github.com/h0nde/roblox-group-scraper/archive/main.zip
- Set up config.json to your preference
- Add your HTTP/S proxies to proxies.txt
- Launch scraper.bat
