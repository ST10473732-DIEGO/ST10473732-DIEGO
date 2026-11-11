# Automatic GitHub profile

The `Update GitHub profile` Actions workflow refreshes the statistics and Pac-Man contribution calendar at minute 17 of every hour (GitHub scheduling may delay runs). It also runs after changes to `tools/` or its workflow, or manually through Actions → Update GitHub profile → Run workflow.

The workflow uses GitHub's built-in `GITHUB_TOKEN`. No personal token or external service is required. The token has repository contents-write permission so it can update only the generated assets it stages. No credentials are stored in the artwork or source.

## What updates

- Contributions, attributed commits and pull requests over the last year.
- Owned public repositories excluding forks, their stars, and followers.
- Daily contribution squares and the SVG Pac-Man animation.

The programming languages and biography are manually supplied profile information, not inferred usage statistics. To change these, edit `assets/diego-profile.svg` and the biography in `README.md`.

The workflow uses the contribution data visible to its token. Private activity may differ from the count seen when signed into your account. It never fetches or publishes private repository names or code. Local commits do not appear until pushed, and GitHub's contribution eligibility and processing rules still apply.

This is scheduled refresh, not a webhook on every repository you contribute to. Updates elsewhere appear after GitHub processes them and the next workflow runs. GitHub may cache README images briefly. Bot-generated commits do not re-trigger this workflow. If data has not changed, it makes no commit.

## If an update fails

Open Actions → Update GitHub profile → the failed run and inspect its log. The workflow fails instead of replacing live data with invented values. Check that GitHub Actions is enabled and branch rules permit `github-actions[bot]` to commit. Public-repository schedules may be disabled after 60 days of repository inactivity; re-enable through Actions if necessary.

## Local validation

`python3 -m unittest discover -s tools -p 'test_*.py'`

To render a local test fixture without accessing GitHub: `python3 tools/update_profile.py --input fixture.json --output /tmp/profile-preview`. Keep test fixture output outside `assets/`; production uses the live API.
