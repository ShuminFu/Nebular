export PYTHONHOME="$(dirname $(dirname $(realpath $(which python))))"
export PATH=$(dirname $(realpath $(which python))):$PATH