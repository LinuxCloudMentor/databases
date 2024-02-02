import os

def download_mysql_from_url(url, version, arch):
    tar_filename = f"mysql-{version}-1.el9.{arch}.rpm-bundle.tar"

    # Check if the file is already downloaded
    if not os.path.exists(tar_filename):
        print(f"Downloading MySQL {version} from {url}...")
        os.system(f"wget {url}")
    else:
        print(f"MySQL {version} package already downloaded.")

    # Create the directory if it doesn't exist
    target_directory = f"mysql-{version}-1.el9.{arch}.rpm-bundle"
    os.makedirs(target_directory, exist_ok=True)

    # Extract the tar file into the specified directory if not already extracted
    if not os.listdir(target_directory):
        os.system(f"tar -xvf {tar_filename} -C {target_directory}")
        print(f"MySQL {version} package untarred successfully.")
    else:
        print(f"MySQL {version} package already untarred.")

    # Run removal commands in the target directory
    os.system(f"rm -rf {target_directory}/*debug* {target_directory}/*test*")

def create_mysql_users(root_password):
    # Loop for creating MySQL users
    while True:
        new_username = input("Enter new MySQL username (type 'stop' to finish): ")
        if new_username.lower() == 'stop':
            break

        if new_username:
            new_password = input(f"Enter password for '{new_username}': ")
            user_host = input(f"Enter host for '{new_username}' (e.g., %, localhost, 192.168.1.1): ")

            # Create a new MySQL user
            os.system(f"sudo mysql -u root -p'{root_password}' -e \"CREATE USER '{new_username}'@'{user_host}' IDENTIFIED BY '{new_password}';\"")

            # Grant necessary privileges to the user
            os.system(f"sudo mysql -u root -p'{root_password}' -e \"GRANT ALL PRIVILEGES ON *.* TO '{new_username}'@'{user_host}' WITH GRANT OPTION;\"")

            print(f"User '{new_username}'@'{user_host}' created successfully.")
        else:
            print("Username cannot be empty. Please try again.")

def install_mysql_packages(version, arch):
    print(f"Installing MySQL {version} packages...")

    # Install all MySQL packages from the target directory
    target_directory = f"mysql-{version}-1.el9.{arch}.rpm-bundle"
    all_packages = f"{target_directory}/mysql-community-*.rpm"
    os.system(f"sudo yum localinstall -y {all_packages}")

def configure_mysql(version, port, root_username, root_password, my_cnf_parameters):
    print("Configuring MySQL...")

    # Allow the specified port in SELinux
    os.system(f"sudo semanage port -a -t mysqld_port_t -p tcp {port}")

    # Allow the specified port in firewall
    os.system(f"sudo firewall-cmd --permanent --add-port={port}/tcp && sudo firewall-cmd --reload")

    # Add parameters to my.cnf
    my_cnf_path = "/etc/my.cnf"
    additional_parameters = f"""
#[group_concat_max_len]
#group_concat_max_len = 512M

[mysqld]
#sql-mode = "STRICT_TRANS_TABLES,NO_ZERO_IN_DATE,NO_ZERO_DATE,ERROR_FOR_DIVISION_BY_ZERO,NO_ENGINE_SUBSTITUTION"
#max_allowed_packet = 1G
#max_connections = 1000
#innodb_rollback_on_timeout=ON
#innodb_lock_wait_timeout=120
#interactive_timeout = 600
#wait_timeout = 180
#net_read_timeout = 600
#net_write_timeout = 600
#connect_timeout= 60
#key_buffer_size  = 16M
#read_buffer_size = 1M
#read_rnd_buffer_size = 1M
#sort_buffer_size = 1M
port = {port}
"""

    # Append additional parameters to my.cnf
    with open(my_cnf_path, 'a') as my_cnf_file:
        my_cnf_file.write(additional_parameters)

    # Restart MySQL service
    os.system("sudo service mysqld restart")

    # Grep root password from MySQL log file
    log_file_path = "/var/log/mysqld.log"
    grep_command = f"sudo grep 'temporary password' {log_file_path} | awk '{{print $NF}}'"
    result = os.popen(grep_command).read().strip()
    
    if not result:
        print("Unable to retrieve the temporary root password from the log file.")
        return

    temp_root_password = result

    # Update the root password
    os.system(f"sudo mysqladmin -u root -p'{temp_root_password}' password {root_password}")

    # Restart MySQL service
    os.system("sudo service mysqld restart")

    # Create MySQL users
    create_mysql_users(root_password)

    # Flush privileges
    os.system(f"sudo mysql -u root -p'{root_password}' -e \"FLUSH PRIVILEGES;\"")

    # Restart MySQL service
    os.system("sudo service mysqld restart")


def main():
    mysql_version = input("Enter MySQL version (e.g., 8.1.0, 8.2.0): ")
    mysql_arch = "x86_64"  # Default architecture
    mysql_port = input("Enter MySQL port: ")
    root_username = input("Enter MySQL root username: ")
    root_password = input("Enter password for MySQL root user: ")

    download_url = f"https://downloads.mysql.com/archives/get/p/23/file/mysql-{mysql_version}-1.el9.{mysql_arch}.rpm-bundle.tar"
    download_mysql_from_url(download_url, mysql_version, mysql_arch)

    install_mysql_packages(mysql_version, mysql_arch)
    configure_mysql(mysql_version, mysql_port, root_username, root_password, my_cnf_parameters=None)

    print("MySQL installation and configuration completed successfully.")

    # Print the output of SELECT user, host FROM mysql.user;
    os.system(f"sudo mysql -u root -p'{root_password}' -e \"SELECT user, host FROM mysql.user;\"")
    print("MySQL installation and configuration completed successfully.")
    print("Maintainer : https://www.youtube.com/@linuxcloudMentor")
    print(" Tank you :)")

if __name__ == "__main__":
    main()
