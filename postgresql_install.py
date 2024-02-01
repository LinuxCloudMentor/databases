import os
import getpass
import subprocess
import urllib.request


def install_postgresql_packages(postgresql_version, arch):
    print(f"Installing PostgreSQL {postgresql_version} packages...")
    os.system(f"wget https://download.postgresql.org/pub/repos/yum/reporpms/EL-9-x86_64/pgdg-redhat-repo-latest.noarch.rpm -P /tmp")
    os.system(f"sudo dnf install -y /tmp/pgdg-redhat-repo-latest.noarch.rpm")


    # Install PostgreSQL server package
    os.system(f"sudo yum install -y postgresql{postgresql_version}-server")

    # Initialize PostgreSQL data directory
    initdb_command = f"sudo /usr/pgsql-{postgresql_version}/bin/postgresql-{postgresql_version}-setup initdb"
    os.system(initdb_command)
    service_name = f"postgresql-{postgresql_version}.service"
    restart_command = f"sudo systemctl restart {service_name}"
    os.system(restart_command)

def configure_postgresql(port, postgresql_version, superuser, superuser_password, postgresql_port):
    print("Configuring PostgreSQL...")

    # Check if the PostgreSQL service is installed
    service_name = f"postgresql-{postgresql_version}.service"
    if os.system(f"systemctl is-active --quiet {service_name}") != 0:
        print(f"PostgreSQL service ({service_name}) not found. Please make sure PostgreSQL is installed.")
        return

    postgresql_conf_path = f"/var/lib/pgsql/{postgresql_version}/data/postgresql.conf"
    pg_hba_conf_path = f"/var/lib/pgsql/{postgresql_version}/data/pg_hba.conf"
    additional_parameters = f"\nport = {port}\n"

    # Append additional parameters to postgresql.conf
    with open(postgresql_conf_path, 'a') as postgresql_conf_file:
        postgresql_conf_file.write(additional_parameters)
        postgresql_conf_file.write("listen_addresses = '*'\n")

    # Update pg_hba.conf to allow connections from any IP
    with open(pg_hba_conf_path, 'a') as pg_hba_conf_file:
        pg_hba_conf_file.write("\n# Allow connections from any IP\n")
        pg_hba_conf_file.write("local   all             postgres                                trust\n")
        pg_hba_conf_file.write("local   all             all                                     trust\n")
        pg_hba_conf_file.write("host    all             all             0.0.0.0/0               trust\n")
        pg_hba_conf_file.write("host    all             all             ::1/128                 trust\n")

    # Delete lines containing "scram-sha-256" from pg_hba.conf
    with open(pg_hba_conf_path, 'r+') as pg_hba_conf_file:
        lines = pg_hba_conf_file.readlines()
        pg_hba_conf_file.seek(0)
        pg_hba_conf_file.truncate()
        for line in lines:
            if "scram-sha-256" not in line:
                pg_hba_conf_file.write(line)

    # Delete lines containing "peer" from pg_hba.conf
    with open(pg_hba_conf_path, 'r+') as pg_hba_conf_file:
        lines = pg_hba_conf_file.readlines()
        pg_hba_conf_file.seek(0)
        pg_hba_conf_file.truncate()
        for line in lines:
            if "peer" not in line:
                pg_hba_conf_file.write(line)

    # Restart PostgreSQL service
    restart_command = f"sudo systemctl restart {service_name}"
    os.system(restart_command)

    # Update the password for the superuser
    update_postgresql_superuser_password(superuser_password, postgresql_port)

    # Create PostgreSQL users
    create_postgresql_user(superuser, superuser_password, postgresql_port)

def create_postgresql_user(username, password, postgresql_port):
    # Check if the user already exists
    check_user_command = [
        "psql",
        "-U", "postgres",
        "-d", "postgres",
        "-h", "localhost",
        "-p", str(postgresql_port),
        "-t", "-c", f"SELECT 1 FROM pg_roles WHERE rolname = '{username}';"
    ]
    user_exists = subprocess.run(check_user_command, stdout=subprocess.PIPE).stdout.decode().strip() == '1'

    if user_exists:
        print(f"User '{username}' already exists. Skipping user creation.")
    else:
        # Create a new PostgreSQL user
        create_user_command = [
            "psql",
            "-U", "postgres",
            "-d", "postgres",
            "-h", "localhost",
            "-p", str(postgresql_port),
            "-c", f"CREATE USER {username} WITH PASSWORD '{password}';"
        ]
        try:
            subprocess.run(create_user_command, check=True)
            print(f"User '{username}' created successfully.")
        except subprocess.CalledProcessError as e:
            print(f"Error creating user '{username}': {e}")

        # Grant necessary privileges to the user
        grant_privileges_command = [
            "psql",
            "-U", "postgres",
            "-d", "postgres",
            "-h", "localhost",
            "-p", str(postgresql_port),
            "-c", f"GRANT ALL PRIVILEGES ON DATABASE postgres TO {username};"
        ]
        try:
            subprocess.run(grant_privileges_command, check=True)
            print(f"Privileges granted to user '{username}' successfully.")
        except subprocess.CalledProcessError as e:
            print(f"Error granting privileges to user '{username}': {e}")

        # Update user with superuser, createdb, and createrole privileges
        update_user_command = [
            "psql",
            "-U", "postgres",
            "-d", "postgres",
            "-h", "localhost",
            "-p", str(postgresql_port),
            "-c", f"ALTER USER {username} WITH SUPERUSER CREATEDB CREATEROLE;"
        ]
        try:
            subprocess.run(update_user_command, check=True)
            print(f"User '{username}' updated with superuser, createdb, and createrole privileges.")
        except subprocess.CalledProcessError as e:
            print(f"Error updating user '{username}': {e}")

def update_postgresql_superuser_password(superuser_password, postgresql_port):
    # Update the password for the PostgreSQL superuser
    update_password_command = [
        "psql",
        "-U", "postgres",
        "-d", "postgres",
        "-h", "localhost",
        "-p", str(postgresql_port),
        "-c", f"ALTER USER postgres WITH PASSWORD '{superuser_password}';"
    ]
    try:
        subprocess.run(update_password_command, check=True)
        print("Password for PostgreSQL superuser 'postgres' updated successfully.")
    except subprocess.CalledProcessError as e:
        print(f"Error updating password for PostgreSQL superuser: {e}")

def create_postgresql_user_interactively(postgresql_port):
    while True:
        new_username = input("Enter new PostgreSQL username (type 'stop' to finish): ")
        if new_username.lower() == 'stop' or not new_username:
            break

        new_password = getpass.getpass(f"Enter password for '{new_username}': ")

        create_postgresql_user(new_username, new_password, postgresql_port)

def allow_port_in_selinux(postgresql_port):
    # Allow the PostgreSQL port in SELinux
    sealert_command = f"semanage port -a -t postgresql_port_t -p tcp {postgresql_port}"
    os.system(sealert_command)

def add_firewall_rule(postgresql_port):
    # Add firewall rule to allow traffic on the PostgreSQL port
    firewall_command = f"sudo firewall-cmd --add-port={postgresql_port}/tcp --permanent && sudo firewall-cmd --reload"
    os.system(firewall_command)

    disable_postgreSQL_module = f"sudo dnf -qy module disable postgresql"
    os.system(disable_postgreSQL_module)

def main():
    postgresql_version = input("Enter PostgreSQL version (e.g., 14,15,16): ")
    postgresql_port = input("Enter PostgreSQL port: ")
    postgresql_superuser = "postgres"  # Hardcoded PostgreSQL superuser

    # Ask for the superuser password
    postgresql_superuser_password = getpass.getpass(f"Enter the password for PostgreSQL superuser '{postgresql_superuser}': ")

    # Install PostgreSQL packages and initialize data directory
    try:
        install_postgresql_packages(postgresql_version, "x86_64")
    except Exception as e:
        print(f"Error installing PostgreSQL packages: {str(e)}")
        return

    # Configure PostgreSQL
    try:
        configure_postgresql(postgresql_port, postgresql_version, postgresql_superuser, postgresql_superuser_password, postgresql_port)
    except Exception as e:
        print(f"Error configuring PostgreSQL: {str(e)}")
        return

    # Create PostgreSQL users interactively
    create_postgresql_user_interactively(postgresql_port)

    # Allow port in SELinux
    allow_port_in_selinux(postgresql_port)

    # Add firewall rule
    add_firewall_rule(postgresql_port)

    # Print the output of SELECT rolname FROM pg_roles;
    subprocess.run(["psql", "-U", "postgres", "-h", "localhost", "-p", postgresql_port, "-d", "postgres", "-c", "SELECT DISTINCT rolname, rolcreatedb FROM pg_roles WHERE rolcreatedb IS NOT NULL ORDER BY rolcreatedb DESC;"])

    # Replace "trust" with "md5" in pg_hba.conf
    replace_trust_with_md5(postgresql_version)

def replace_trust_with_md5(postgresql_version):
    pg_hba_conf_path = f"/var/lib/pgsql/{postgresql_version}/data/pg_hba.conf"

    # Replace "trust" with "md5" using sed
    replace_command = f"sudo sed -i 's/trust/md5/g' {pg_hba_conf_path}"
    os.system(replace_command)

    # Restart PostgreSQL service
    service_name = f"postgresql-{postgresql_version}.service"
    restart_command = f"sudo systemctl restart {service_name}"
    os.system(restart_command)
    print("PostgreSQL installation and configuration completed successfully.")
    print("Maintainer : https://www.youtube.com/@linuxcloudMentor")
    print(" Tank you :)")

if __name__ == "__main__":
    main()

