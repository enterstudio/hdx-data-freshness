# -*- coding: utf-8 -*-
'''
Unit tests for the freshness class.

'''
import os
from os.path import join

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool

from hdx.freshness.database.dbdataset import DBDataset
from hdx.freshness.database.dbinfodataset import DBInfoDataset
from hdx.freshness.database.dborganization import DBOrganization
from hdx.freshness.database.dbresource import DBResource
from hdx.freshness.database.dbrun import DBRun
from hdx.freshness.datafreshness import DataFreshness
from hdx.freshness.testdata.dbtestresult import DBTestResult
from hdx.freshness.testdata.serialize import deserialize_now, deserialize_datasets, deserialize_results, \
    deserialize_hashresults
from hdx.freshness.testdata.testbase import TestBase


class TestFreshnessDay0:
    @pytest.fixture(scope='function')
    def nodatabase(self):
        dbpath = join('tests', 'test_freshness.db')
        try:
            os.remove(dbpath)
        except FileNotFoundError:
            pass
        return 'sqlite:///%s' % dbpath

    @pytest.fixture(scope='class')
    def serializedbsession(self):
        dbpath = join('tests', 'fixtures', 'day0', 'test_serialize.db')
        engine = create_engine('sqlite:///%s' % dbpath, poolclass=NullPool, echo=False)
        Session = sessionmaker(bind=engine)
        TestBase.metadata.create_all(engine)
        return Session()

    @pytest.fixture(scope='function')
    def now(self, serializedbsession):
        return deserialize_now(serializedbsession)

    @pytest.fixture(scope='function')
    def datasets(self, serializedbsession):
        return deserialize_datasets(serializedbsession)

    @pytest.fixture(scope='function')
    def results(self, serializedbsession):
        return deserialize_results(serializedbsession)

    @pytest.fixture(scope='function')
    def hash_results(self, serializedbsession):
        return deserialize_hashresults(serializedbsession)

    @pytest.fixture(scope='function')
    def forced_hash_ids(self, serializedbsession):
        forced_hash_ids = serializedbsession.query(DBTestResult.id).filter_by(force_hash=1)
        return [x[0] for x in forced_hash_ids]

    def test_generate_dataset(self, configuration, nodatabase, now, datasets, results, hash_results, forced_hash_ids,
                              resourcecls):
        freshness = DataFreshness(db_url=nodatabase, datasets=datasets, now=now)
        datasets_to_check, resources_to_check = freshness.process_datasets(forced_hash_ids=forced_hash_ids)
        results, hash_results = freshness.check_urls(resources_to_check, results=results, hash_results=hash_results)
        datasets_lastmodified = freshness.process_results(results, hash_results, resourcecls=resourcecls)
        freshness.update_dataset_last_modified(datasets_to_check, datasets_lastmodified)
        output = freshness.output_counts()
        assert output == '''
*** Resources ***
* total: 660 *,
adhoc-revision: 44,
internal-revision: 56,
revision: 508,
revision,api: 4,
revision,error: 27,
revision,hash: 8,
revision,http header: 13

*** Datasets ***
* total: 103 *,
0: Fresh, Updated metadata: 66,
0: Fresh, Updated metadata,revision,http header: 8,
2: Overdue, Updated metadata: 1,
3: Delinquent, Updated metadata: 18,
3: Delinquent, Updated metadata,error: 5,
3: Delinquent, Updated metadata,revision,http header: 1,
Freshness Unavailable, Updated metadata: 4

15 datasets have update frequency of Live
19 datasets have update frequency of Never
0 datasets have update frequency of Adhoc'''

        dbsession = freshness.session
        dbrun = dbsession.query(DBRun).one()
        assert str(dbrun) == '<Run number=0, Run date=2017-12-18 16:03:33.208327>'
        dbresource = dbsession.query(DBResource).first()
        assert str(dbresource) == '''<Resource(run number=0, id=b21d6004-06b5-41e5-8e3e-0f28140bff64, name=Topline Numbers.csv, dataset id=a2150ad9-2b87-49f5-a6b2-c85dff366b75,
url=https://docs.google.com/spreadsheets/d/e/2PACX-1vRjFRZGLB8IMp0anSGR1tcGxwJgkyx0bTN9PsinqtaLWKHBEfz77LkinXeVqIE_TsGVt-xM6DQzXpkJ/pub?gid=0&single=true&output=csv,
error=None, last modified=2017-12-16 15:11:15.202742, what updated=revision,hash,
revision last updated=2017-12-16 15:11:15.202742, http last modified=None, MD5 hash=None, when hashed=2017-12-18 16:03:33.208327, when checked=2017-12-18 16:03:33.208327, api=False)>'''
        count = dbsession.query(DBResource).filter_by(what_updated='adhoc-revision', error=None, api=None).count()
        assert count == 44
        count = dbsession.query(DBResource).filter(DBResource.url.like('%data.humdata.org%')).count()
        assert count == 56
        count = dbsession.query(DBResource).filter_by(what_updated='internal-revision', error=None, api=None).count()
        assert count == 56
        count = dbsession.query(DBResource).filter_by(what_updated='internal-revision,hash', error=None, api=False).count()
        assert count == 0
        count = dbsession.query(DBResource).filter_by(what_updated='internal-revision,http header,hash', error=None, api=False).count()
        assert count == 0
        count = dbsession.query(DBResource).filter_by(what_updated='revision', error=None, api=None).count()
        assert count == 508
        count = dbsession.query(DBResource).filter_by(what_updated='revision', error=None, api=True).count()
        assert count == 4
        count = dbsession.query(DBResource).filter(DBResource.error.isnot(None)).filter_by(what_updated='revision').count()
        assert count == 27
        count = dbsession.query(DBResource).filter_by(what_updated='revision,hash', error=None, api=False).count()
        assert count == 8
        count = dbsession.query(DBResource).filter_by(what_updated='revision,http header', error=None, api=None).count()
        assert count == 13
        count = dbsession.query(DBResource).filter_by(what_updated='revision,http header,hash', error=None, api=False).count()
        assert count == 0
        dbdataset = dbsession.query(DBDataset).first()
        assert str(dbdataset) == '''<Dataset(run number=0, id=a2150ad9-2b87-49f5-a6b2-c85dff366b75, dataset date=09/21/2017, update frequency=1,
last_modified=2017-12-16 15:11:15.204215what updated=metadata, metadata_modified=2017-12-16 15:11:15.204215,
Resource b21d6004-06b5-41e5-8e3e-0f28140bff64: last modified=2017-12-16 15:11:15.202742,
Dataset fresh=2'''
        count = dbsession.query(DBDataset).filter_by(fresh=0, what_updated='metadata', error=False).count()
        assert count == 66
        count = dbsession.query(DBDataset).filter_by(fresh=0, what_updated='metadata', error=True).count()
        assert count == 0
        count = dbsession.query(DBDataset).filter_by(fresh=0, what_updated='metadata,revision,http header', error=False).count()
        assert count == 8
        count = dbsession.query(DBDataset).filter_by(fresh=0, what_updated='metadata,revision,http header', error=True).count()
        assert count == 0
        count = dbsession.query(DBDataset).filter_by(fresh=1, what_updated='metadata').count()
        assert count == 0
        count = dbsession.query(DBDataset).filter_by(fresh=2, what_updated='metadata', error=False).count()
        assert count == 1
        count = dbsession.query(DBDataset).filter_by(fresh=2, what_updated='metadata', error=True).count()
        assert count == 0
        count = dbsession.query(DBDataset).filter_by(fresh=3, what_updated='metadata', error=False).count()
        assert count == 18
        count = dbsession.query(DBDataset).filter_by(fresh=3, what_updated='metadata', error=True).count()
        assert count == 5
        count = dbsession.query(DBDataset).filter_by(fresh=3, what_updated='metadata,revision,http header').count()
        assert count == 1
        count = dbsession.query(DBDataset).filter_by(fresh=None, what_updated='metadata', error=False).count()
        assert count == 4
        count = dbsession.query(DBDataset).filter_by(fresh=None, what_updated='metadata', error=True).count()
        assert count == 0
        dbinfodataset = dbsession.query(DBInfoDataset).first()
        assert str(dbinfodataset) == '''<InfoDataset(id=a2150ad9-2b87-49f5-a6b2-c85dff366b75, name=rohingya-displacement-topline-figures, title=Rohingya Displacement Topline Figures,
private=False, organization id=hdx,
maintainer=7d7f5f8d-7e3b-483a-8de1-2b122010c1eb, maintainer email=takavarasha@un.org, author=None, author email=None, location=bgd)>'''
        count = dbsession.query(DBInfoDataset).count()
        assert count == 103
        dborganization = dbsession.query(DBOrganization).first()
        assert str(dborganization) == '''<Organization(id=hdx, name=hdx, title=HDX)>'''
        count = dbsession.query(DBOrganization).count()
        assert count == 40
