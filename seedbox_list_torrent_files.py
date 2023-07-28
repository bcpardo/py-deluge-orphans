import paramiko, re, os, os.path
'''
This script will compare active torrents in Deluge and downloaded data on a host to find orphaned files. 
It assumes downloads are in the Downloads folder in the home directory and deluge-console is in bin.
It also assumes there is a public/private key pair set up with the host.
'''

hostname = 'moon.usbx.me' # enter seedbox host
username = 'bron7' # enter seedbox user
keyfile = "/home/brian/.ssh/usbx" # Change to the location of your local private key

# Given a file path, this function returns the directory and the extension of the file.
def get_directory_and_extension(filepath):
    directory, filename = os.path.split(filepath)
    basename, extension = os.path.splitext(filename)
    return directory, extension

# Establishes and returns an SSH connection using provided hostname, username, and private key file.
def ssh_connect(hostname, username, keyfile):
    pkey = paramiko.RSAKey.from_private_key_file(keyfile)  # Load private key from file
    connection = paramiko.SSHClient()  # Create an SSH client
    connection.set_missing_host_key_policy(paramiko.AutoAddPolicy())  # Allow auto-adding of unknown host keys
    connection.connect(hostname, username = username, pkey = pkey)  # Connect to the host
    return connection


# Executes a given command on a remote host via SSH and returns the result and any error message.
def ssh_command(host, command):
    stdin, stdout, stderr = host.exec_command(command) # Execute the command
    stdin.close() # Close the input stream
    result = stdout.read().decode("utf-8", "ignore") # Read and decode the command result
    error = stderr.read().decode() # Read and decode any error message
    return result, error

# Writes each item from a given list to a new line in the specified file.
def write_file(filename, data_list):
    with open(filename, 'w') as f:
        for item in data_list:
            f.write("%s\n" % item)

# The deluge-console info command returns filenames with size, progress, and priority information at the end.
# Cleans up the filename by removing uneeded information added by the cli command.
def deluge_filename_cleanup(filename):
    pattern = r"(.*)(?=\s\(\d+(\.\d+)?\s[GMK]?iB\) Progress: \d+(\.\d+)?% Priority: (High|Medium|Low))"
    filename_cleaned = re.match(pattern, filename).group(1)  # Match and extract the cleaned filename using regex
    filename_cleaned = filename_cleaned.strip()  # Strip leading and trailing whitespace
    return filename_cleaned

# Extracts list of files from torrent data, cleaning up each filename using deluge_filename_cleanup().
def extract_torrent_files(torrent_data):
    start_file_list = 0
    torrent_files = []
    for torrent_file in torrent_data:
        if "::Peers" in torrent_file and start_file_list == 1:
            start_file_list = 0  # Stop adding files when the "Peers" section is reached
        elif "::Files" in torrent_file and start_file_list == 0:
            start_file_list = 1  # Start adding files when the "Files" section is reached
        elif start_file_list == 1 and torrent_file:
            torrent_file = deluge_filename_cleanup(torrent_file)  # Clean up the filename
            torrent_files.append(torrent_file)  # Add the cleaned file to the list
    return torrent_files


# Retrieves a list of files from a remote host and cleans up filenames based on the specified command.
def get_clean_file_list(host, command):
    raw_list, errors = ssh_command(host, command)  # Execute the command on the host
    raw_list = raw_list.split("\n")  # Split the raw output into a list of lines
    if "deluge-console" in command: # If the command was for deluge-console, extract torrent files
        final_list = extract_torrent_files(raw_list) 
    elif "Downloads" in command: # If the command was for Downloads, trim off the "Downloads/" prefix
        final_list = [list_item[len("Downloads/"):] for list_item in raw_list if list_item] 
    return final_list

# Compares download and torrent file lists, returning download files not present in torrent files, excluding specific types.
def list_compare(download_files, torrent_files):
    results = []
    archive_file_directories = set()

    for filepath in torrent_files:
        directory, extension = get_directory_and_extension(filepath)  # Extract directory and extension
        if extension in ['.zip', '.rar', '.tar']: # Add directory to set if file is an archive
            archive_file_directories.add(directory)

    # Ignore files that are:
    # 1. Found in the active torrent files list
    # 2. A video file that is in the same directory as an archive file in active torrent file list, most likely this was extracted
    for filepath in download_files:
        if filepath not in torrent_files:
            directory, extension = get_directory_and_extension(filepath)  # Extract directory and extension
            if not (extension in ['.mp4', '.avi', '.mkv'] and directory in archive_file_directories):
                results.append(filepath)  # Add file to results if not present in torrent files

    return results

# Main function that connects to an SSH server, retrieves and compares file lists, and writes the results to files.
def main(hostname, username, keyfile):
    server = ssh_connect(hostname, username, keyfile)  # Establish SSH connection to the server

    torrent_files = get_clean_file_list(server, "bin/deluge-console 'connect 127.0.0.1:11906 ; info -v'")  # Get list of torrent files
    download_files = get_clean_file_list(server, "find Downloads -type f")  # Get list of download files

    downloads_not_active = list_compare(download_files, torrent_files)  # Compare lists to find inactive downloads
    active_not_downloaded = [filepath for filepath in torrent_files if filepath not in download_files]  # Find active torrents not in downloads

    downloads_not_active = sorted(downloads_not_active)  # Sort results
    active_not_downloaded = sorted(active_not_downloaded)  # Sort results

    write_file('active_torrents.txt', torrent_files)  # Write torrent files to a text file
    write_file('downloads.txt', download_files)  # Write download files to a text file
    write_file('orphans.txt', downloads_not_active)  # Write inactive downloads to a text file
    write_file('active_missing_file.txt', active_not_downloaded)  # Write active torrents not in downloads to a text file

main(hostname, username, keyfile)