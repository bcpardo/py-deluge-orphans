import paramiko, re, os, os.path
'''
This script will compare active torrents in Deluge and downloaded data on a host to find orphaned files. 
It assumes downloads are in the Downloads folder in the home directory and deluge-console is in bin.
It also assumes there is a public/private key pair set up with the host.
'''

hostname = 'moon.usbx.me'
username = 'bron7'
keyfile = "/home/brian/.ssh/usbx"

def get_directory_and_extension(filepath):
    directory, filename = os.path.split(filepath)
    basename, extension = os.path.splitext(filename)
    return directory, extension

def ssh_connect(hostname, username, keyfile):
    pkey = paramiko.RSAKey.from_private_key_file(keyfile) # Private key file location
    connection = paramiko.SSHClient()
    connection.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    connection.connect(hostname, username = username, pkey = pkey)
    return connection

def ssh_command(host, command):
    stdin, stdout, stderr = host.exec_command(command)
    stdin.close()
    result = stdout.read().decode("utf-8", "ignore")
    error = stderr.read().decode()
    return result, error

def deluge_filename_cleanup(filename):
    pattern = r"(.*)(?=\s\(\d+(\.\d+)?\s[GMK]?iB\) Progress: \d+(\.\d+)?% Priority: (High|Medium|Low))"
    filename_cleaned = re.match(pattern, filename).group(1)
    filename_cleaned = filename_cleaned.strip()
    return filename_cleaned

def extract_torrent_files(torrent_data):
    start_file_list = 0
    torrent_files = []
    for torrent_file in torrent_data.split("\n"):
        if "::Peers" in torrent_file and start_file_list == 1:
            start_file_list = 0
        elif "::Files" in torrent_file and start_file_list == 0:
            start_file_list = 1
        elif start_file_list == 1 and torrent_file:
            torrent_file = deluge_filename_cleanup(torrent_file)
            torrent_files.append(torrent_file)
    return torrent_files

server = ssh_connect(hostname, username, keyfile)

get_torrents_command = "bin/deluge-console 'connect 127.0.0.1:11906 ; info -v'"
get_downloads_command = "find Downloads -type f"

torrent_list, torrent_errors = ssh_command(server, get_torrents_command)
download_list, download_errors = ssh_command(server, get_downloads_command)

torrent_files = extract_torrent_files(torrent_list)

downloads_cleaned = []

for download in download_list.split("\n"):
    download_cleaned = download[len("Downloads/"):]
    downloads_cleaned.append(download_cleaned)

downloads_cleaned = [item for item in downloads_cleaned if item]

torrent_files_directories = set(get_directory_and_extension(filepath)[0] for filepath in torrent_files)
torrent_files_archives = set(filepath for filepath in torrent_files if get_directory_and_extension(filepath)[1] in ['.zip', '.rar', '.tar'])

torrent_files = sorted(torrent_files)
downloads_cleaned = sorted(downloads_cleaned)

downloads_not_active = [filepath for filepath in downloads_cleaned if filepath not in torrent_files]
downloads_not_active = [
    filepath for filepath in downloads_not_active
    if not (get_directory_and_extension(filepath)[1] in ['.mp4', '.avi', '.mkv'] and
            get_directory_and_extension(filepath)[0] in torrent_files_directories and
            any(os.path.commonpath([filepath, archive]) == get_directory_and_extension(filepath)[0] for archive in torrent_files_archives))
]

active_not_downloaded = [filepath for filepath in torrent_files if filepath not in downloads_cleaned]

downloads_not_active = sorted(downloads_not_active)
active_not_downloaded = sorted(active_not_downloaded)

with open('active_torrents.txt', 'w') as f:
    for torrent in torrent_files:
        f.write("%s\n" % torrent)

with open('downloads.txt', 'w') as f:
    for downloaded in downloads_cleaned:
        f.write("%s\n" % downloaded)

with open('orphans.txt', 'w') as f:
    for download_orphan in downloads_not_active:
        f.write("%s\n" % download_orphan)

with open('active_missing_file.txt', 'w') as f:
    for missing_file in active_not_downloaded:
        f.write("%s\n" % missing_file)