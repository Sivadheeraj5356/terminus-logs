CREATE DATABASE IF NOT EXISTS helix_catalog;
USE helix_catalog;

CREATE USER IF NOT EXISTS 'helix'@'localhost' IDENTIFIED BY 'helix';
CREATE USER IF NOT EXISTS 'helix'@'127.0.0.1' IDENTIFIED BY 'helix';
GRANT ALL PRIVILEGES ON helix_catalog.* TO 'helix'@'localhost';
GRANT ALL PRIVILEGES ON helix_catalog.* TO 'helix'@'127.0.0.1';
FLUSH PRIVILEGES;

CREATE TABLE IF NOT EXISTS dependency_approvals (
  package_name VARCHAR(64) PRIMARY KEY,
  approved_version VARCHAR(32) NOT NULL,
  approval_status ENUM('approved', 'pending', 'rejected') NOT NULL
);

CREATE TABLE IF NOT EXISTS platform_constraints (
  id INT AUTO_INCREMENT PRIMARY KEY,
  package_name VARCHAR(64) NOT NULL,
  os VARCHAR(32) NOT NULL,
  arch VARCHAR(32) NOT NULL,
  min_version VARCHAR(32) NOT NULL,
  max_version VARCHAR(32) NOT NULL,
  UNIQUE KEY uniq_pkg_platform (package_name, os, arch)
);
