#!/bin/bash
cd "$(dirname "$0")"
java -Xmx2G -Xms1G -jar paper.jar nogui
