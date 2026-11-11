import copy
import datetime as dt
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import update_profile as profile


def fixture():
    end = dt.date(2026, 11, 11)
    start = end - dt.timedelta(days=364)
    weeks, week = [], []
    for i in range(365):
        date = start + dt.timedelta(days=i)
        weekday = (date.weekday() + 1) % 7
        if weekday == 0 and week:
            weeks.append({'contributionDays':week})
            week=[]
        count = (i*7 % 11) if i % 3 == 0 else 0
        level = 0 if count == 0 else min(4, 1+count//3)
        week.append({'date':date.isoformat(),'weekday':weekday,'contributionCount':count,'contributionLevel':profile.LEVELS[level]})
    if week:weeks.append({'contributionDays':week})
    total=sum(d['contributionCount'] for w in weeks for d in w['contributionDays'])
    return {'login':profile.OWNER,'followers':1,'public_repos':8,'stars':12,'commits':100,'pull_requests':4,'issues':2,'reviews':1,'calendar':{'totalContributions':total,'weeks':weeks}}

class ProfileTests(unittest.TestCase):
    def test_calendar_and_animation(self):
        data=fixture()
        profile.validate_profile(data)
        svg=profile.calendar_svg(data)
        profile.validate_svg(svg)
        self.assertEqual(svg.count(' contributions</title>'),365)
        self.assertIn('<animateMotion',svg)
        self.assertNotIn('<script',svg)
        self.assertIn(f"{data['calendar']['totalContributions']:,} contributions",svg)

    def test_zero_activity_renders(self):
        data=fixture()
        for week in data['calendar']['weeks']:
            for day in week['contributionDays']:
                day.update(contributionCount=0,contributionLevel='NONE')
        data['calendar']['totalContributions']=0
        profile.validate_profile(data)
        profile.validate_svg(profile.calendar_svg(data))

    def test_bad_data_preserves_existing_artwork(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)
            profile.write_assets(fixture(),path)
            before={p.name:p.read_bytes() for p in path.iterdir()}
            bad=fixture();bad['calendar']['totalContributions']+=1
            with self.assertRaises(ValueError):profile.write_assets(bad,path)
            self.assertEqual(before,{p.name:p.read_bytes() for p in path.iterdir()})

    def test_unchanged_data_produces_identical_svg(self):
        data=fixture()
        self.assertEqual(profile.calendar_svg(data),profile.calendar_svg(copy.deepcopy(data)))
        self.assertEqual(profile.stats_svg(data),profile.stats_svg(copy.deepcopy(data)))

    def test_pagination_includes_all_public_repository_stars(self):
        collection={'totalCommitContributions':1,'totalPullRequestContributions':2,'totalIssueContributions':3,'totalPullRequestReviewContributions':4,'contributionCalendar':fixture()['calendar']}
        first={'login':profile.OWNER,'followers':{'totalCount':5},'contributionsCollection':collection,'repositories':{'totalCount':102,'nodes':[{'stargazerCount':1} for _ in range(100)],'pageInfo':{'hasNextPage':True,'endCursor':'next-page'}}}
        second={'repositories':{'nodes':[{'stargazerCount':5},{'stargazerCount':7}],'pageInfo':{'hasNextPage':False,'endCursor':'done'}}}
        with patch.object(profile,'graphql',side_effect=[first,second]) as call:
            data=profile.fetch_profile('test-token',profile.OWNER)
            self.assertEqual(data['stars'],112)
            self.assertEqual(data['public_repos'],102)
            self.assertEqual(call.call_args.args,('test-token',profile.OWNER,'next-page'))

    def test_rejects_wrong_weekday_and_duplicate_date(self):
        data=fixture();day=data['calendar']['weeks'][0]['contributionDays'][0]
        day['weekday']=(day['weekday']+1)%7
        with self.assertRaises(ValueError):profile.validate_profile(data)
        data=fixture();days=data['calendar']['weeks'][0]['contributionDays'];days[1]=copy.deepcopy(days[0])
        with self.assertRaises(ValueError):profile.validate_profile(data)

if __name__=='__main__':unittest.main()
