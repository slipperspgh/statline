name: Update NFL data

on:
  schedule:
    - cron: "0 12 * * *"            # every day at 12:00 UTC
    - cron: "0 16,20 * * 0,1,4"     # extra runs on Sun, Mon, Thu (game days)
  workflow_dispatch:                 # lets you run it by hand from the Actions tab

permissions:
  contents: write

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - run: pip install nflreadpy pandas pyarrow
      - run: python build_data.py
      - run: |
          git config user.name "statline-bot"
          git config user.email "statline-bot@users.noreply.github.com"
          git add data/nfl.json
          git commit -m "Update data" || exit 0
          git push

After committing both, go to Actions, then “Update NFL data,” then “Run workflow.” If it fails again, send me the lines starting at Traceback.

it keeps broingin up the same mesage\

That message (“exit code 1”) is only a generic failure notice, and I can’t see the real reason without more detail. So I’ve changed the schedule file to save the full error into a file in your repository, which is much easier to open than the Actions logs.

Replace everything in .github/workflows/update-data.yml with this:

yaml
name: Update NFL data

on:
  schedule:
    - cron: "0 12 * * *"            # every day at 12:00 UTC
    - cron: "0 16,20 * * 0,1,4"     # extra runs on Sun, Mon, Thu (game days)
  workflow_dispatch:                 # lets you run it by hand from the Actions tab

permissions:
  contents: write

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - run: pip install nflreadpy pandas pyarrow
      - name: Build data
        id: build
        continue-on-error: true
        run: |
          mkdir -p data
          python build_data.py 2>&1 | tee data/log.txt
          exit ${PIPESTATUS[0]}
      - name: Save results
        run: |
          git config user.name "statline-bot"
          git config user.email "statline-bot@users.noreply.github.com"
          git add data
          git commit -m "Update data" || exit 0
          git push
      - name: Fail if the build failed
        if: steps.build.outcome == 'failure'
        run: exit 1
