#! /usr/bin/gawk -f

# Take a .sql file from phpMyAdmin and massage it so it can be directly imported into sqlite
#
# (env) [register]$ scripts/fix-sql.awk devices_superlab_au-20240423-a.sql > devices_superlab_au.sql
# (env) [register]$ cd pyproj/
# (env) [pyproj]$ ./manage.py dbshell < ../devices_superlab_au.sql 
# (env) [pyproj]$ 
#
# This script also creates a superuser with email address 'mjd@afork.com', and massages usernames.

# Define the array of substitutions
BEGIN {
    SKIP = 0
    SQLITE = 1
    MYSQL = 0
}

# Perform substitutions on each line
SKIP == 0 {
    if (SQLITE) {
        # Remove statements sqlite doesn't understand
        sub(/^SET .*/, "-- " $0)

        # Modify statements sqlite nearly understands
        sub(/^START TRANSACTION;/, "BEGIN TRANSACTION;")
    if (MYSQL) {
        if (match($0, /^START TRANSACTION;/)) {
            print("SET FOREIGN_KEY_CHECKS=0;");
        }
    }

    # Fix table names
    $0 = gensub(/(CREATE TABLE|INSERT INTO) `clients`/, "\\1 `device_client`", "g", $0)
    $0 = gensub(/(CREATE TABLE|INSERT INTO) `device_types`/, "\\1 `device_design`", "g", $0)
    $0 = gensub(/(CREATE TABLE|INSERT INTO) `devices`/, "\\1 `device_device`", "g", $0)
    $0 = gensub(/(CREATE TABLE|INSERT INTO) `users`/, "\\1 `authuser_user`", "g", $0)
    $0 = gensub(/(CREATE TABLE|INSERT INTO) `users_clients`/, "\\1 `device_client_users`", "g", $0)

    # Fix column names
    $0 = gensub(/(INSERT INTO `device_client`) \(`Serial`, `Company`, `Logo`\) (VALUES)/, "\\1 (`id`, `company_name`) \\2", "g", $0)
    $0 = gensub(/(INSERT INTO `device_design`) \(`Serial`, `ClientSerial`, `SKU`, `Name`, `Version`\) (VALUES)/, "\\1 (`id`, `client_id`, `sku`, `name`, `version`) \\2", "g", $0)
    $0 = gensub(/(INSERT INTO `device_device`) \(`Serial`, `DeviceTypeSerial`, `AssembledDate`, `Notes`\) (VALUES)/, "\\1 (`id`, `design_id`, `assembly_date`, `notes`) \\2", "g", $0)
    $0 = gensub(/(INSERT INTO `authuser_user`) \(`Serial`, `FirstName`, `LastName`, `Email`, `PasswordHash`\) (VALUES)/, "\\1 (`id`, `preferred_name`, `full_name`, `email`, `password`, `is_active`, `is_staff`, `is_superuser`, `date_joined`) \\2", "g", $0)
    $0 = gensub(/(INSERT INTO `device_client_users`) \(`Serial`, `UserSerial`, `ClientSerial`\) (VALUES)/, "\\1 (`id`, `user_id`, `client_id`) \\2", "g", $0)

    # Fix up of data
    $0 = gensub("'', 'Notes'\\),", "'1-Jan-1970', 'Notes'),", "g", $0) # Missing assembly dates
    $0 = gensub("('[^']*'), ''\\)", "\\1\\)", "g", $0) # Empty logos for clients
    if (SQLITE) {
        $0 = gensub(/(\.tv|\.com\.au)'(\)[,;])$/, "\\1', 'invalid', 1, 0, 0, DATE('now')\\2", "g", $0) # Additional user info
    }
    if (MYSQL) {
        $0 = gensub(/(\.tv|\.com\.au)'(\)[,;])$/, "\\1', 'invalid', 1, 0, 0, CURDATE()\\2", "g", $0) # Additional user info
    }

    # Add some data fixing scripts
    if (match($0, /^COMMIT;/)) {
        # Change assembly dates from dd-mmm-yyyy format, to yyyy-mm-dd format
        print("UPDATE device_device SET assembly_date = ");
        print("    substr(assembly_date, -4) || '-' || ");
        print("    CASE substr(assembly_date, instr(assembly_date, '-') + 1, 3)");
        print("        WHEN 'Jan' THEN '01'");
        print("        WHEN 'Feb' THEN '02'");
        print("        WHEN 'Mar' THEN '03'");
        print("        WHEN 'Apr' THEN '04'");
        print("        WHEN 'May' THEN '05'");
        print("        WHEN 'Jun' THEN '06'");
        print("        WHEN 'Jul' THEN '07'");
        print("        WHEN 'Aug' THEN '08'");
        print("        WHEN 'Sep' THEN '09'");
        print("        WHEN 'Oct' THEN '10'");
        print("        WHEN 'Nov' THEN '11'");
        print("        WHEN 'Dec' THEN '12'");
        print("    END || '-' || substr('0' || substr(assembly_date, 1, instr(assembly_date, '-') - 1), -2);");

        # Fix usernames
        print("UPDATE authuser_user SET full_name = preferred_name || ' ' || full_name;")
        print("UPDATE authuser_user SET preferred_name = 'Jon' WHERE preferred_name = 'Jonathan';");
        print("INSERT INTO `authuser_user` (`id`, `preferred_name`, `full_name`, `email`, `password`, `is_active`, `is_staff`, `is_superuser`, `date_joined`) VALUES")
        if (SQLITE) {
            print("(100, 'Mitch', 'Mitch Davis', 'mjd@afork.com', 'pbkdf2_sha256$720000$2ve6S2XB6rBLFEbJsd09vm$4ZnXsPDjUhq2JNtr7jiox0abT3yRCr5hFszzZw/WjbE=', 1, 1, 1, DATE('now'));")
        }
        if (MYSQL) {
        print("(100, 'Mitch', 'Mitch Davis', 'mjd@afork.com', 'pbkdf2_sha256$720000$2ve6S2XB6rBLFEbJsd09vm$4ZnXsPDjUhq2JNtr7jiox0abT3yRCr5hFszzZw/WjbE=', 1, 1, 1, CURDATE());")
        }
    }

    # Don't save transaction (optional, for testing)
    # sub(/^COMMIT;/, "ROLLBACK;")

    # Change CREATE TABLEs to DELETE FROMs, and skip ALTER TABLEs
    if (match($0, /^(CREATE TABLE|ALTER TABLE)/)) {
        if (match($0, /^CREATE TABLE `([^`]*)`/, a)) {
            print("DELETE FROM `" a[1] "`;")
        }
        SKIP = 1
        next
    }
    print
}

# If in skip mode and we find a semicolon, stop skipping
SKIP == 1 && /;$/ {
    SKIP = 0
}
