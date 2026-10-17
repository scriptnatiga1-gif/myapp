name: Build APK
on: [push]
jobs:
  build:
    runs-on: ubuntu-20.04
    steps:
      - uses: actions/checkout@v4
      - name: Set up Python 3.8
        uses: actions/setup-python@v4
        with:
          python-version: '3.8'
      - name: Install dependencies
        run: |
          sudo apt update
          sudo apt install -y python3-pip zip unzip openjdk-8-jdk libffi-dev libssl-dev libltdl-dev libbz2-dev libsqlite3-dev
          pip install --upgrade pip
          pip install Cython==0.29.33 buildozer
      - name: Build APK
        run: |
          buildozer android debug --verbose
      - name: Upload APK
        uses: actions/upload-artifact@v4
        with:
          name: apk-working
          path: bin/*.apk
