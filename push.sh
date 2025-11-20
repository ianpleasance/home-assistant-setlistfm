#!/bin/bash
VER=$(grep 'version' custom_components/*/manifest.json | awk -F':' '{print $2}')
VER=$(echo ${VER} | awk -F'"' '{print $2}')
echo ${VER}
git push
git tag -a v${VER} -m "Version ${VER}"
git push origin v${VER}

