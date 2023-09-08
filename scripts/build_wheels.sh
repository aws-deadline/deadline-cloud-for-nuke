#!/bin/bash
# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

if [ ! -d wheels ]; then
    mkdir wheels
fi
rm wheels/*

for dir in ../openjobio ../deadline-cloud ../deadline-cloud-for-nuke; do
    echo "Building $dir..."    
    cd $dir
    hatch build
    mv dist/* ../deadline-cloud-for-nuke/wheels/
done
