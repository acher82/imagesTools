import sys
from os import listdir, rename
from os.path import isfile, join

if len(sys.argv) == 1:
    print("Provide a path")
    sys.exit(1)

mypath = sys.argv[1]
print(mypath)

only_files = [f for f in listdir(mypath) if isfile(join(mypath, f))]
for file in only_files:
    if "-" not in file:
        continue
    new_name = file.replace("-", "_")
    rename(join(mypath, file), join(mypath, new_name))
    print(file, new_name)
