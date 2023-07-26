'''
This script will compare active torrents in Deluge and downloaded data on a host to find orphaned files. 
It assumes downloads are in the Downloads folder in the home directory and deluge-console is in bin.
It also assumes there is a public/private key pair set up with the host.
'''
import paramiko, re

server = 'moon.usbx.me'
username = 'bron7'
pkey = paramiko.RSAKey.from_private_key_file("/home/brian/.ssh/usbx") # Private key file location

get_torrents_command = "bin/deluge-console 'connect 127.0.0.1:11906 ; info -v'"
get_downloads_command = "find Downloads -type f"

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect( server, username = username, pkey = pkey )
ssh_torrents_stdin, ssh_torrents_stdout, ssh_torrents_stderr = ssh.exec_command(get_torrents_command)
ssh_downloads_stdin, ssh_downloads_stdout, ssh_downloads_stderr = ssh.exec_command(get_downloads_command)

torrent_list = ssh_torrents_stdout.read().decode()
download_list = ssh_downloads_stdout.read().decode("utf-8","ignore")
torrent_errors = ssh_torrents_stderr.read().decode()
download_errors = ssh_downloads_stderr.read().decode()

ssh_torrents_stdin.close()
ssh_downloads_stdin.close()

start_file_list = 0
files = []

for line in torrent_list.split("\n"):
    line_stripped = line.strip()
    if line_stripped.startswith("::Peers") and start_file_list == 1:
        start_file_list = 0
    elif line_stripped.startswith("::Files") and start_file_list == 0:
        start_file_list = 1
    elif start_file_list == 1:
        files.append(line_stripped)

files_cleaned = []
downloads_cleaned = []

pattern = r"(.*)(?=\s\(\d+(\.\d+)?\s[GMK]?iB\) Progress: \d+(\.\d+)?% Priority: (High|Medium|Low))"
for filename in files:
    filename_cleaned = re.match(pattern, filename).group(1)
    files_cleaned.append(filename_cleaned)

for download in download_list.split("\n"):
    download_cleaned = download[len("Downloads/"):]
    downloads_cleaned.append(download_cleaned)

files_cleaned = [item for item in files_cleaned if item]
downloads_cleaned = [item for item in downloads_cleaned if item]

files_cleaned = sorted(files_cleaned)
downloads_cleaned = sorted(downloads_cleaned)

downloads_not_active = list(set(downloads_cleaned) - set(files_cleaned))
active_not_downloaded = list(set(files_cleaned) - set(downloads_cleaned))

downloads_not_active = sorted(downloads_not_active)
active_not_downloaded = sorted(active_not_downloaded)


with open('active_torrents.txt', 'w') as f:
    for torrent in files_cleaned:
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