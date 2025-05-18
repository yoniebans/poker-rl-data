#!/bin/bash
# Simple script to extract all zip files in a directory recursively

# Check if directory argument is provided
if [ $# -lt 1 ]; then
  echo "Usage: $0 <directory>"
  echo "Example: $0 /nous/poker_data/2025-05-04_STA_NL100_SH_LXUBI280"
  exit 1
fi

INPUT_DIR="$1"
echo "Looking for zip files in $INPUT_DIR..."

# Find and extract all zip files
find "$INPUT_DIR" -type f -name "*.zip" | while read zip_file; do
  # Create directory based on zip file name
  dir_name=$(dirname "$zip_file")/$(basename "$zip_file" .zip)
  
  # Create the directory if it doesn't exist
  mkdir -p "$dir_name"
  
  echo "Extracting: $zip_file to $dir_name"
  unzip -o -q "$zip_file" -d "$dir_name"
done

echo "All zip files extracted!"