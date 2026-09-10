"""Small synthetic fixtures exercise v0.3 without sources, network or a live DB."""
from copy import deepcopy
from pathlib import Path
import sys

import numpy as np
from PIL import Image
import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
# Reuse the existing fixture and in-memory store; do not duplicate an experiment framework.
from test_artificial_fragment_experiment import page, MemoryStore
from src.evaluation.artificial_fragment_experiment import build_specification as v02_spec, measure_regions
from src.evaluation.artificial_fragment_registration import register_records, task_identity
from src.evaluation.corpus_audit import inspect_page, sha256_file
from src.evaluation.experiment_database import assert_registration_sources
from src.evaluation.source_availability import availability
from src.evaluation.structured_damage import (
  VERSION, FAMILIES, SEVERITIES, SEVERITY_TOLERANCE, DamageRejected, parameters, build_damage_mask, topology,
)
from src.evaluation.structured_fragment_experiment import (
  build_specification, generate_task, registration_records, compare, metrics,
)


@pytest.mark.parametrize('family', FAMILIES)
@pytest.mark.parametrize('severity', SEVERITIES)
def test_family_calibration_topology_and_deterministic_bytes(family, severity):
  p = parameters('fixture', 'a'*64, family, severity)
  before = deepcopy(p)
  im, stats = build_damage_mask((96, 128), p, severity)
  repeated, again = build_damage_mask((96, 128), deepcopy(p), severity)
  assert p == before == parameters('fixture', 'a'*64, family, severity)
  assert im.tobytes() == repeated.tobytes() and stats == again
  assert stats['removed_pixels'] == round(96*128*severity)
  assert stats['absolute_severity_error'] <= min(SEVERITY_TOLERANCE, .5/(96*128))
  assert stats['topology']['passed'] and stats['topology']['removed_components'] == 1
  assert stats['measured_severity'] + stats['surviving_fraction'] == 1
  assert topology(im, p) == stats['topology']


@pytest.mark.parametrize('edge', ('top', 'bottom', 'left', 'right'))
@pytest.mark.parametrize('family', ('edge_loss', 'edge_tear'))
def test_every_edge_orientation(edge, family):
  p = parameters('p','b'*64,family,.6); p['edge'] = edge
  im, stats = build_damage_mask((67, 93),p,.6)
  assert stats['topology']['touched_edges'] == [edge]
  if family == 'edge_tear':
    assert stats['topology']['positive_depth_levels'] >= 3


@pytest.mark.parametrize('corner', ('top_left', 'top_right', 'bottom_left', 'bottom_right'))
def test_every_corner(corner):
  p = parameters('p','b'*64,'corner_loss',.6); p['corner'] = corner
  _, stats = build_damage_mask((67,93),p,.6)
  assert set(stats['topology']['touched_edges']) == set(corner.split('_'))


@pytest.mark.parametrize('orientation', ('vertical','horizontal'))
@pytest.mark.parametrize('placement', ('start_edge','interior','end_edge'))
def test_strip_placement_and_orientation(orientation, placement):
  p=parameters('p','c'*64,'strip_loss',.6);p.update(orientation=orientation,placement=placement)
  _, stats=build_damage_mask((96,171),p,.6)
  assert stats['topology']['checks']['full_orientation_span']
  assert stats['topology']['checks']['contiguous_cross_sections']
  assert stats['topology']['normalized_elongation'] > 1.25


def test_mask_families_are_not_aliases():
  masks=[build_damage_mask((96,128),parameters('page','c'*64,f,.3),.3)[0].tobytes() for f in FAMILIES]
  assert len(set(masks)) == len(FAMILIES)


@pytest.mark.parametrize('family', FAMILIES)
def test_small_page_rejected_instead_of_relaxing_topology(family):
  with pytest.raises(DamageRejected,match='dimensions'):
    build_damage_mask((3,5),parameters('p','a'*64,family,.6),.6)


def test_unrealizable_severity_rejected_and_disconnected_mask_fails():
  p=parameters('p','d'*64,'internal_hole',.99)
  with pytest.raises(DamageRejected,match='capacity'):
    build_damage_mask((16,16),p,.99)
  im=Image.new('L',(40,40),0); im.paste(255,(2,2,5,5));im.paste(255,(30,30,35,35))
  result=topology(im,parameters('p','d'*64,'connected_piece_loss',.3))
  assert not result['passed'] and result['removed_components']==2


def test_validation_matrix_rejections_and_restoration_preserve_v02(tmp_path,page):
  saved=v02_spec([page]); original=deepcopy(saved)
  source=(tmp_path/'source.png').read_bytes();(tmp_path/'source.png').unlink()
  missing=inspect_page(tmp_path,page)
  frozen_v02=v02_spec([missing]);frozen_copy=deepcopy(frozen_v02)
  excluded=build_specification([missing,dict(page,page_id='test',split='test'),dict(page,page_id='train',split='train')])
  assert excluded['matrix_task_count']==0
  assert excluded['rejected_pages']==[{'page_id':'page','reasons':['missing_artifact:source.png']}]
  (tmp_path/'source.png').write_bytes(source)
  restored=inspect_page(tmp_path,page)
  selected=build_specification([restored,dict(page,split='test',page_id='test')])
  assert selected['selected_page_count']==1 and selected['matrix_task_count']==12
  assert saved==original and frozen_v02==frozen_copy
  assert {e['page_id'] for e in selected['tasks']}=={'page'}
  assert len({e['task_id'] for e in selected['tasks']})==12
  assert not {e['task_id'] for e in saved['tasks']} & {e['task_id'] for e in selected['tasks']}


def test_deterministic_explicit_task_rejection(page):
  p=dict(page,dimensions_px=[5,5]);spec=build_specification([p])
  assert spec['selected_page_count']==1 and spec['conceptual_matrix_task_count']==12
  assert spec['matrix_task_count']==0 and len(spec['rejected_tasks'])==12
  assert spec==build_specification([deepcopy(p)])


def test_generation_registration_rerun_and_source_invariants(tmp_path,page):
  original=deepcopy(page);spec=build_specification([page])
  tasks=[generate_task(tmp_path,page,e) for e in spec['tasks']]
  first=deepcopy(tasks)
  stamps={r['path']:(tmp_path/r['path']).stat().st_mtime_ns for t in tasks for r in t['artifacts'].values()}
  assert [generate_task(tmp_path,page,e) for e in spec['tasks']]==first
  assert stamps=={path:(tmp_path/path).stat().st_mtime_ns for path in stamps}
  assert page==original and sha256_file(tmp_path/'source.png')==page['source_sha256']
  records=registration_records(tmp_path,spec,tasks);assert_registration_sources(records,[page])
  store=MemoryStore(page)
  assert register_records(store,records)['inserted']==12
  frozen=deepcopy(store.rows)
  assert register_records(store,records)['matched']==12 and store.rows==frozen and store.writes==12
  assert len({task_identity(t)[0] for t in tasks})==12
  for t in tasks:
    assert t['source_provenance']['registered_source_record']['corpus_page']==page['source_record']
    assert t['source_provenance']['registered_source_record']['database_asset']['training_allowed'] is False
    assert t['layout_survival_estimate']['regions'][0]['source_region_area_px']==300  # Full mask, not bbox.
    with Image.open(tmp_path/t['artifacts']['fragment_image']['path']) as im:
      arr=np.asarray(im)
      assert (arr[arr[:,:,3]==0] == 0).all()  # No hidden source RGB leaks in transparent missing areas.
  changed=deepcopy(page);changed['database_asset']['training_allowed']=True
  with pytest.raises(ValueError,match='provenance_or_rights'):
    assert_registration_sources(records,[changed])
  changed['split']='test'
  with pytest.raises(ValueError,match='not_valid_validation'):
    assert_registration_sources(records,[changed])
  with pytest.raises(ValueError,match='incomplete_or_duplicate'):
    registration_records(tmp_path,spec,tasks+[tasks[0]])
  tampered=deepcopy(tasks);tampered[0]['parameters']['mask_parameters']['edge']='not_an_edge'
  with pytest.raises(ValueError,match='parameters_mismatch'):
    registration_records(tmp_path,spec,tampered)
  tampered=deepcopy(tasks);tampered[0]['split_name']='test'
  with pytest.raises(ValueError,match='validation_split'):
    registration_records(tmp_path,spec,tampered)


@pytest.mark.parametrize('split',('train','test'))
def test_no_generation_from_excluded_splits(tmp_path,page,split):
  entry=build_specification([page])['tasks'][0]
  with pytest.raises(ValueError,match='only_valid_validation'):
    generate_task(tmp_path,dict(page,split=split),entry)
  assert not (tmp_path/'outputs').exists()


def test_orientation_and_identity_bind_scientific_inputs(page):
  spec=build_specification([page]);changed=deepcopy(page);changed['source_sha256']='f'*64
  assert build_specification([changed])['tasks']!=spec['tasks']
  assert spec==build_specification([deepcopy(page)])


def test_multiple_classes_and_mask_alignment(tmp_path,page):
  d=deepcopy(page['detections'][0]);d.update(index=1,label='Gloss',class_id=12)
  survival=Image.new('L',(120,100),0);survival.paste(255,(0,0,60,100))
  regions=measure_regions(tmp_path,[page['detections'][0],d],survival,'run')
  assert [r['label'] for r in regions]==['Main script black','Gloss']
  assert all(r['surviving_area_px']==100 and r['removed_area_px']==200 for r in regions)
  with pytest.raises(ValueError):
    measure_regions(tmp_path,[d],Image.new('L',(10,10),255),'run')


def test_matched_comparison_excludes_new_pages_and_keeps_thresholds():
  def t(id,page,version,family,f):
    return {'task_id':id,'source_sample_id':page,'experiment_version':version,'mask_family':family,
      'requested_severity':.3,'measured_severity':.3,'surviving_fraction':.7,'manuscript_id':'m',
      'layout_survival_estimate':{'regions':[{'label':'Text','surviving_fraction':f}]}}
  tasks=[t('a','old',VERSION,'edge_loss',1),t('b','restored',VERSION,'edge_loss',0)]
  controls=[t('c','old','artificial_fragment_experiment_v0_2','rectangular',.5)]
  result=compare(tasks,controls)
  assert result['matched_page_ids']==['old']
  assert result['all_v03']['overall']['region_survival']['mean']==.5
  assert result['matched_comparison'][VERSION]['overall']['region_survival']['mean']==1
  assert metrics(tasks)['mostly_surviving_region_rate']==metrics(tasks)['almost_complete_survival_rate']==.5


def test_restoration_only_promotes_exact_registered_bytes(tmp_path,page):
  original=deepcopy(page);payload=(tmp_path/'source.png').read_bytes();(tmp_path/'source.png').unlink()
  page['source_record']['image']['download_url']='https://example.test/exact.png'
  calls=[]
  def download(url,destination,**kwargs):
    calls.append(url);destination.write_bytes(payload)
  dry=availability(tmp_path,[page],downloader=download)
  assert dry['counts']['unavailable_local']==1 and not calls
  result=availability(tmp_path,[page],restore=True,previous=dry,downloader=download)
  assert result['counts']['restored_checksum_verified']==1 and len(calls)==1
  assert availability(tmp_path,[page],previous=result,downloader=download)==result
  assert (tmp_path/'source.png').read_bytes()==payload
  assert page['source_record']['image']['training_allowed'] is False
  assert page['split']==original['split'] and page['database_asset']==original['database_asset']
  assert not list((tmp_path/'outputs').rglob('*.part'))


def test_mismatched_download_never_replaces_original_placeholder(tmp_path,page):
  (tmp_path/'source.png').unlink();page['source_record']['image']['download_url']='https://example.test/exact.png'
  def wrong(url,destination,**kwargs): destination.write_bytes(b'wrong bytes')
  result=availability(tmp_path,[page],restore=True,downloader=wrong)
  assert result['counts']['restoration_failed']==1
  assert result['pages'][0]['reason']=='registered_checksum_mismatch'
  assert not (tmp_path/'source.png').exists()


def test_readable_mismatched_source_requires_manual_action(tmp_path,page):
  (tmp_path/'source.png').write_bytes(b'wrong')
  result=availability(tmp_path,[page],restore=True,downloader=lambda *a,**k: pytest.fail('must not download'))
  assert result['counts']['requires_manual_action']==1
  assert (tmp_path/'source.png').read_bytes()==b'wrong'


def test_identical_local_copy_restored_without_network(tmp_path,page):
  (tmp_path/'data').mkdir();(tmp_path/'source.png').rename(tmp_path/'data/copy.png')
  result=availability(tmp_path,[page],restore=True,downloader=lambda *a,**k: pytest.fail('no network'))
  assert result['counts']['restored_checksum_verified']==1
  assert result['pages'][0]['identical_local_copies']==['data/copy.png']
  assert result['pages'][0]['restoration']['mechanism']=='checksum_identical_local_copy'


def test_placeholder_search_finds_exact_local_copy(tmp_path,page,monkeypatch):
  import src.evaluation.source_availability as module
  source=tmp_path/'source.png';payload=source.read_bytes()
  (tmp_path/'data').mkdir();(tmp_path/'data/exact.png').write_bytes(payload)
  source.write_bytes(bytes(len(payload)))
  real_state=module.local_state
  def state(path):
    return {'exists':True,'dataless':True} if path==source and path.read_bytes()==bytes(len(payload)) else real_state(path)
  monkeypatch.setattr(module,'local_state',state)
  result=availability(tmp_path,[page],restore=True,downloader=lambda *a,**k: pytest.fail('exact local bytes must win'))
  assert result['pages'][0]['initial_state']['dataless'] is True
  assert result['pages'][0]['current_state']['dataless'] is False
  assert result['pages'][0]['identical_local_copies']==['data/exact.png']
  assert source.read_bytes()==payload
