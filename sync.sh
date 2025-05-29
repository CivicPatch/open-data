#!/bin/bash

set -e

git config --global user.email "civicpatch-pipeline@civicpatch.org"
git config --global user.name "CivicPatch Pipeline"

git checkout main
git pull origin main

mkdir tmp

git clone --depth 1 --no-checkout https://github.com/CivicPatch/civicpatch-tools.git tmp
cd tmp
git sparse-checkout init --cone
git sparse-checkout set civpatch/data civpatch/data_source
git checkout

cd ..

# Copy the files under tmp/data & tmp/data_source into the data & data_source folders
cp -r tmp/civpatch/data/* data/
cp -r tmp/civpatch/data_source/* data_source/

# Remove the tmp folder
rm -rf tmp

# If there are any changes, commit them
git add data/
git add data_source/

if git diff --quiet --staged; then
  echo "No changes to commit"
else
  DATE=$(date +%Y-%m-%d)
  git commit -m "Sync from CivicPatch - $DATE"
  git push origin main
fi
