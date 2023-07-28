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

def write_file(filename, list):
    with open(filename, 'w') as f:
        for item in list:
            f.write("%s\n" % item)

def deluge_filename_cleanup(filename):
    pattern = r"(.*)(?=\s\(\d+(\.\d+)?\s[GMK]?iB\) Progress: \d+(\.\d+)?% Priority: (High|Medium|Low))"
    filename_cleaned = re.match(pattern, filename).group(1)
    filename_cleaned = filename_cleaned.strip()
    return filename_cleaned

def extract_torrent_files(torrent_data):
    start_file_list = 0
    torrent_files = []
    for torrent_file in torrent_data:
        if "::Peers" in torrent_file and start_file_list == 1:
            start_file_list = 0
        elif "::Files" in torrent_file and start_file_list == 0:
            start_file_list = 1
        elif start_file_list == 1 and torrent_file:
            torrent_file = deluge_filename_cleanup(torrent_file)
            torrent_files.append(torrent_file)
    return torrent_files

def get_clean_file_list(host, command):
    raw_list, errors = ssh_command(host, command)
    raw_list = raw_list.split("\n")
    if "deluge-console" in command:
        final_list = extract_torrent_files(raw_list)
    elif "Downloads" in command:
        final_list = [list_item[len("Downloads/"):] for list_item in raw_list if list_item]
    return final_list

def list_compare(download_files, torrent_files):
    results = []
    torrent_files_directories = set(get_directory_and_extension(item)[0] for item in torrent_files)
    torrent_files_archives = set(filepath for filepath in torrent_files if get_directory_and_extension(filepath)[1] in ['.zip', '.rar', '.tar'])
    results = [filepath for filepath in download_files if filepath not in torrent_files]
    results = [
        filepath for filepath in results
        if not (get_directory_and_extension(filepath)[1] in ['.mp4', '.avi', '.mkv'] and
                get_directory_and_extension(filepath)[0] in torrent_files_directories and
                any(os.path.commonpath([filepath, archive]) == get_directory_and_extension(filepath)[0] for archive in torrent_files_archives))
            ]
    return results

def main():
    server = ssh_connect(hostname, username, keyfile)

    torrent_files = get_clean_file_list(server, "bin/deluge-console 'connect 127.0.0.1:11906 ; info -v'")
    download_files = get_clean_file_list(server, "find Downloads -type f")

    downloads_not_active = list_compare(download_files, torrent_files)
    active_not_downloaded = [filepath for filepath in torrent_files if filepath not in download_files]

    downloads_not_active = sorted(downloads_not_active)
    active_not_downloaded = sorted(active_not_downloaded)

    write_file('active_torrents.txt', torrent_files)
    write_file('downloads.txt', download_files)
    write_file('orphans.txt', downloads_not_active)
    write_file('active_missing_file.txt', active_not_downloaded)

main()