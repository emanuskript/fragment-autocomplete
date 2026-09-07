"""Small synthetic validation fixtures; no model, network, or repository binaries."""
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
import json
import sys
from uuid import NAMESPACE_URL, uuid5

import pytest
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from src.evaluation.artificial_fragments import GENERATION_VERSION, sha256_file
from src.evaluation.artificial_fragment_experiment import (
  EXPERIMENT_VERSION, SURVIVAL_THRESHOLDS, aggregate, build_specification, generate_task,
  mask_overlap, measure_regions, registration_records, survival_category, task_paths,
)
from src.evaluation.artificial_fragment_registration import SourceDatabaseContext, register_records
from src.evaluation.corpus_audit import (
  artifact, audit_corpus, digest, distribution, inspect_page, read_region_mask, review_outliers, write_stable,
)
from src.evaluation.experiment_database import assert_registration_sources


def uid(name):
  return str(uuid5(NAMESPACE_URL, name))


@pytest.fixture
def page(tmp_path):
  Image.new('RGB', (120, 100), 'tan').save(tmp_path / 'source.png')
  mask = Image.new('L', (120, 100), 0)
  # Two disconnected regions deliberately extend outside the reported bbox.
  mask.paste(255, (5, 5, 15, 15))
  mask.paste(255, (90, 80, 110, 90))
  mask.save(tmp_path / 'region.png')
  d = {'index': 0, 'class_id': 4, 'label': 'Main script black', 'confidence': .6,
       'bbox_xyxy': [5, 5, 15, 15], 'mask_path': 'region.png', 'mask_sha256': sha256_file(tmp_path / 'region.png'),
       'mask_pixel_area': 300, 'mask_dimensions_px': [120, 100], 'db_layout_region_id': uid('region')}
  raw = {'sample_id': 'page', 'status': 'success', 'orig_shape': [100,120], 'detections': [d]}
  write_stable(tmp_path / 'raw.json', raw)
  Image.new('RGB', (120,100), 'tan').save(tmp_path / 'overlay.jpg')
  ids = {'image_asset_id': uid('source'), 'canvas_id': uid('canvas'), 'manuscript_id': uid('manuscript'), 'repository_id': uid('repository')}
  checksum = sha256_file(tmp_path / 'source.png')
  source_record = {'image': {'checksum_sha256': checksum, 'local_path': 'source.png', 'training_allowed': False,
    'rights_review_status': 'pending_review', 'license': 'unknown', 'attribution': 'fixture', 'rights_statement': None}, 'registration': {'db_ids': ids}}
  result = {'status': 'success', 'dataset_split': 'validation', 'db_image_asset_id': ids['image_asset_id'],
    'raw_output_path': 'raw.json', 'overlay_path': 'overlay.jpg', 'detected_region_count': 1}
  p = {'page_id': 'page', 'manuscript_id': 'manuscript', 'split': 'validation', 'corpus_id': 'fixture',
    'canvas_identifier': 'https://example.test/canvas', 'canvas_label': '1r', 'repository': 'fixture', 'provider': 'example.test',
    'source_path': 'source.png', 'source_sha256': checksum, 'source_size_bytes': (tmp_path/'source.png').stat().st_size,
    'dimensions_px': [120,100], 'db_ids': ids, 'source_record': source_record, 'result': result,
    'stored_run': {'db_segmentation_run_id': uid('run'), 'dataset_split': 'validation', 'db_image_asset_id': ids['image_asset_id'], 'layout_region_count': 1},
    'model': {'run_identity_sha256': 'a'*64, 'model_id': 'eManuSkript-fixture'}}
  p = inspect_page(tmp_path, p)
  p['database_asset'] = {'training_allowed': False, 'rights_review_status': 'pending_review', 'raw_metadata': {'source': 'fixture'}}
  return p


def test_validation_selection_matrix_and_deterministic_order(page):
  pages = [dict(page, page_id='test-page', split='test'), page,
           dict(page, page_id='train-page', split='train'), dict(page, page_id='second')]
  spec = build_specification(pages)
  assert spec == build_specification(list(reversed(pages)))
  assert spec['validation_page_count'] == spec['selected_page_count'] == 2
  assert spec['matrix_task_count'] == 2 * len(spec['mask_families']) * len(spec['severities'])
  assert {p['page_id'] for p in spec['selected_pages']} == {'page','second'}
  assert len({t['task_id'] for t in spec['tasks']}) == spec['matrix_task_count']
  assert all(t['rotation_degrees'] == 0 and t['scale'] == 1 for t in spec['tasks'])


def test_explicit_rejection_without_replacement(page):
  bad = dict(page, errors=['missing_segmentation_mask'])
  spec = build_specification([bad, dict(page, page_id='test', split='test')])
  assert spec['matrix_task_count'] == 0
  assert spec['rejected_pages'] == [{'page_id':'page','reasons':['missing_segmentation_mask']}]


def test_empty_successful_segmentation_stays_selected(page):
  p = dict(page, detections=[])
  spec = build_specification([p])
  assert spec['matrix_task_count'] == 4
  assert spec['selected_pages'][0]['layout_status'] == 'no_detected_regions'


@pytest.mark.parametrize('width,expected', [(0,0),(10,.5),(20,1)])
def test_exact_mask_survival_edges(width, expected):
  region = Image.new('L',(20,10),255)
  survival = Image.new('L',(20,10),0)
  if width: survival.paste(255,(0,0,width,10))
  metrics = mask_overlap(region, survival)
  assert metrics['source_region_area_px'] == 200
  assert metrics['surviving_fraction'] == expected
  assert metrics['removed_fraction'] == 1-expected
  assert metrics['surviving_area_px'] + metrics['removed_area_px'] == 200


def test_empty_mask_has_undefined_survival():
  metric = mask_overlap(Image.new('L',(5,5),0),Image.new('L',(5,5),255))
  assert metric['surviving_fraction'] is None
  assert survival_category(None) == 'undefined'


def test_full_mask_includes_pixels_outside_bbox(tmp_path,page):
  survival = Image.new('L',(120,100),255)
  regions = measure_regions(tmp_path, page['detections'], survival, uid('run'))
  assert regions[0]['source_region_area_px'] == regions[0]['surviving_area_px'] == 300
  assert regions[0]['surviving_fraction'] == 1
  assert regions[0]['source_region_identifier'] == uid('run')+':0'
  assert regions[0]['geometry_method'] == 'segmentation_mask'


@pytest.mark.parametrize('corruption', ['checksum','area','dimensions','missing','nonbinary'])
def test_invalid_mask_never_falls_back_to_bbox(tmp_path,page,corruption):
  d = deepcopy(page['detections'][0])
  if corruption == 'checksum': d['mask_sha256'] = '0'*64
  if corruption == 'area': d['mask_pixel_area'] = 301
  if corruption == 'dimensions': d['mask_dimensions_px'] = [1,1]
  if corruption == 'missing': d.pop('mask_path')
  if corruption == 'nonbinary':
    image=Image.open(tmp_path/'region.png').copy(); image.putpixel((0,0),128); image.save(tmp_path/'region.png')
    d['mask_sha256']=sha256_file(tmp_path/'region.png')
  with pytest.raises(ValueError): read_region_mask(tmp_path,d,(120,100))


@pytest.mark.parametrize('fraction,category', [(0,'fully_removed'),(.01,'mostly_destroyed'),(.05,'mostly_destroyed'),(.051,'partial'),(.949,'partial'),(.95,'almost_complete'),(1,'almost_complete')])
def test_central_thresholds(fraction,category):
  assert survival_category(fraction) == category


def test_region_class_aggregation():
  def task(id, fractions, label):
    return {'task_id':id,'mask_family':'irregular','requested_severity':.3,'manuscript_id':'m','source_sample_id':id,
      'surviving_fraction':.7,'layout_survival_estimate':{'regions':[{'label':label,'surviving_fraction':f} for f in fractions]}}
  tasks = [task('one',[0,.05,.5,1],'Main'), task('two',[1],'Gloss')]
  summary = aggregate(tasks)
  assert summary == aggregate(list(reversed(tasks)))
  main = summary['groups']['layout_class']['Main']
  assert main['task_count'] == 1 and main['region_measurement_count'] == 4
  assert main['region_surviving_fraction']['mean'] == pytest.approx(.3875)
  assert all(main['survival_categories'][c]['count'] == 1 for c in ('almost_complete','partial','mostly_destroyed','fully_removed'))
  assert summary['groups']['layout_class']['Gloss']['region_surviving_fraction']['population_standard_deviation'] is None


class MemoryStore:
  def __init__(self,page): self.page,self.rows,self.writes = page,{},0
  def source_context(self,asset):
    p=self.page
    return SourceDatabaseContext(asset,p['db_ids']['canvas_id'],p['source_path'],p['source_sha256'],*p['dimensions_px'])
  def segmentation_run_image_asset_id(self,run): return self.page['db_ids']['image_asset_id']
  def upsert_task(self,record):
    values=record.database_values()
    if record.database_id in self.rows:
      assert self.rows[record.database_id] == values
      return 'matched'
    self.rows[record.database_id]=values; self.writes+=1
    return 'inserted'


def test_generation_checksums_identity_idempotency_and_provenance(tmp_path,page):
  original = deepcopy(page)
  spec=build_specification([page])
  tasks=[generate_task(tmp_path,page,e) for e in spec['tasks']]
  first=[deepcopy(t) for t in tasks]
  tasks=[generate_task(tmp_path,page,e) for e in spec['tasks']]
  assert tasks == first  # Includes every PNG and JSON checksum, transforms, and measurements.
  assert page == original and sha256_file(tmp_path/'source.png') == page['source_sha256']
  assert all(t['generation_version'] == GENERATION_VERSION for t in tasks)
  records=registration_records(tmp_path,spec,tasks)
  assert_registration_sources(records,[page])
  store=MemoryStore(page)
  assert register_records(store,records)['inserted'] == len(spec['tasks'])
  rows=deepcopy(store.rows)
  assert register_records(store,records)['matched'] == len(spec['tasks'])
  assert store.rows == rows and store.writes == len(records)
  assert all(t['split_name'] == 'validation' for t in tasks)
  assert all(t['source_provenance']['registered_source_record']['database_asset']['training_allowed'] is False for t in tasks)
  assert len({r.database_id for r in records}) == len(records)
  with pytest.raises(ValueError,match='incomplete_or_duplicate'): registration_records(tmp_path,spec,tasks+[tasks[0]])
  changed = deepcopy(page); changed['database_asset']['training_allowed']=True
  with pytest.raises(ValueError,match='provenance_or_rights'): assert_registration_sources(records,[changed])
  with pytest.raises(ValueError,match='validation_split'):
    modified=deepcopy(tasks); modified[0]['split_name']='test'; registration_records(tmp_path,spec,modified)


def test_test_page_generation_is_forbidden(tmp_path,page):
  entry=build_specification([page])['tasks'][0]
  with pytest.raises(ValueError,match='only_valid_validation'):
    generate_task(tmp_path,dict(page,split='test'),entry)
  assert not (tmp_path/'outputs').exists()


def test_changed_evidence_changes_identity_and_invalidates_old_spec(tmp_path,page):
  original=build_specification([page])
  changed=deepcopy(page); changed['artifacts'][0]['sha256']='f'*64
  assert build_specification([changed])['tasks'] != original['tasks']
  with pytest.raises(ValueError,match='evidence_changed'):
    generate_task(tmp_path,changed,original['tasks'][0])


def test_audit_and_outlier_review_stability(tmp_path,page):
  manuscripts={'manuscript':{'split':'validation','script':None}}
  audit=audit_corpus([page],manuscripts,[])
  assert audit['structure']['pages_per_split'] == {'train':0,'validation':1,'test':0}
  assert audit['segmentation']['union_mask_fraction_of_source_raster']['mean'] == .025
  path=tmp_path/'audit.json'; write_stable(path,audit); stamp=path.stat().st_mtime_ns
  write_stable(path,audit_corpus([deepcopy(page)],manuscripts,[]))
  assert path.stat().st_mtime_ns == stamp
  evidence=digest(sorted(page['artifacts'],key=lambda a:a['path']))
  decisions={'page':{'classification':'requires_human_review','evidence_sha256':evidence,'note':'Insufficient evidence.'}}
  first=review_outliers([page],{'low_confidence':['page']},decisions)
  assert first == review_outliers([deepcopy(page)],{'low_confidence':['page']},deepcopy(decisions))
  assert first['outliers'][0]['classification']=='requires_human_review'
  decisions['page']['classification']='probable_segmentation_failure'; decisions['page']['evidence_sha256']='stale'
  assert review_outliers([page],{'low_confidence':['page']},decisions)['outliers'][0]['classification']=='requires_human_review'


def test_missing_artifact_is_reported_deterministically(tmp_path,page):
  (tmp_path/'region.png').unlink()
  inspected=inspect_page(tmp_path,page)
  assert inspected['errors'] == ['missing_artifact:region.png']
  assert build_specification([inspected])['rejected_pages'][0]['reasons'] == inspected['errors']


def test_verified_acquired_dimensions_do_not_rewrite_advertised_db_dimensions(monkeypatch,page):
  from scripts.artificial_fragment_experiment import CorpusTaskStore
  from scripts.register_artificial_fragment_tasks import PostgresArtificialFragmentTaskStore
  p=deepcopy(page); p['database_dimensions_px']=[6000,5000]
  original=SourceDatabaseContext(p['db_ids']['image_asset_id'],p['db_ids']['canvas_id'],p['source_path'],p['source_sha256'],6000,5000)
  monkeypatch.setattr(PostgresArtificialFragmentTaskStore,'source_context',lambda self,asset: original)
  result=CorpusTaskStore(None,[p]).source_context(p['db_ids']['image_asset_id'])
  assert (result.width_px,result.height_px)==(120,100)
  assert (original.width_px,original.height_px)==(6000,5000)
  assert p['database_dimensions_px']==[6000,5000]


def test_database_audit_checks_splits_rights_and_mask_provenance(page):
  from src.evaluation.experiment_database import verify_database
  p=deepcopy(page)
  p['source_record']['image'].update(width_px=6000,height_px=5000)
  image=p['source_record']['image']
  ingestion={'manuscript_split':'validation','manuscript_spec_id':'manuscript'}
  asset={**image,'id':p['db_ids']['image_asset_id'],'canvas_id':p['db_ids']['canvas_id'],
    'repository_id':p['db_ids']['repository_id'],'raw_metadata':{'ingestion':ingestion}}
  canvas={'manuscript_id':p['db_ids']['manuscript_id'],'raw_metadata':{'ingestion':ingestion}}
  manuscript={'raw_metadata':{'ingestion':ingestion}}
  run={'id':p['stored_run']['db_segmentation_run_id'],'image_asset_id':asset['id'],'status':'completed',
       'parameters':{'dataset_split':'validation','run_identity_sha256':p['model']['run_identity_sha256']}}
  d=p['detections'][0]
  region={'id':uid('db-region'),'segmentation_run_id':run['id'],'reading_order_index':0,'label':d['label'],
          'label_id':d['class_id'],'mask_path':d['mask_path'],'raw_region':d}
  class Cursor:
    def __init__(self): self.results=iter([[{'asset':asset,'canvas':canvas,'manuscript':manuscript}],[{'run':run}],[region]])
    def execute(self,*args): self.rows=next(self.results)
    def fetchall(self): return deepcopy(self.rows)
  summary=verify_database(Cursor(),[p])
  assert summary['total_layout_regions']==1 and p['errors']==[]
  assert p['detections'][0]['db_layout_region_id']==uid('db-region')
  assert p['database_asset']['training_allowed'] is False
  asset['training_allowed']=True
  with pytest.raises(ValueError,match='rights_mismatch'): verify_database(Cursor(),[deepcopy(p)])


def test_unavailable_source_keeps_segmentation_audit_evidence(tmp_path,page):
  (tmp_path/'source.png').unlink()
  inspected=inspect_page(tmp_path,page)
  assert inspected['errors']==['missing_artifact:source.png']
  assert len(inspected['detections']) == inspected['valid_mask_count'] == 1
  assert inspected['union_mask_area_px']==300
  audit=audit_corpus([inspected],{'manuscript':{'split':'validation'}},[])
  assert audit['segmentation']['total_layout_regions']==1
  assert audit['images']['source_checksum_verified_count']==0
  assert build_specification([inspected])['selected_page_count']==0


def test_registration_binds_actual_source_and_run_to_specification(tmp_path,page):
  spec=build_specification([page])
  tasks=[generate_task(tmp_path,page,e) for e in spec['tasks']]
  wrong_source=deepcopy(tasks); wrong_source[0]['source_image_asset_id']=uid('different-source')
  with pytest.raises(ValueError,match='source_or_run_binding'):
    registration_records(tmp_path,spec,wrong_source)
  wrong_run=deepcopy(tasks)
  wrong_run[0]['layout_survival_estimate']['segmentation_run_provenance']['db_segmentation_run_id']=uid('different-run')
  with pytest.raises(ValueError,match='source_or_run_binding'):
    registration_records(tmp_path,spec,wrong_run)
  wrong_mask=deepcopy(tasks)
  wrong_mask[0]['layout_survival_estimate']['regions'][0]['mask_sha256']='f'*64
  with pytest.raises(ValueError,match='region_mask_binding'):
    registration_records(tmp_path,spec,wrong_mask)
