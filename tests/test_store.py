import json
import time
from concurrent.futures import ThreadPoolExecutor
import pytest


def test_dependency_priority_and_atomic_claim(store, workspace):
    pid=store.project('Sample','Build useful software',workspace)
    first=store.task(pid,'First','Implement first feature',[['python','-V']],priority=1)
    second=store.task(pid,'Second','Implement next feature',[['python','-V']],[first],priority=100)
    with ThreadPoolExecutor(2) as pool:
        claimed=list(pool.map(lambda _:store.claim(), range(2)))
    assert sum(c is not None for c in claimed)==1
    assert next(c for c in claimed if c)['id']==first
    store.update(first,status='completed')
    assert store.claim()['id']==second


def test_recovery_blocks_uncertain_work(store,workspace):
    pid=store.project('Sample','Build useful software',workspace)
    tid=store.task(pid,'Task','Implement useful feature',[['python','-V']])
    store.claim();store.recover()
    task=store.snapshot()['tasks'][0]
    assert task['status']=='blocked'
    assert 'interrupted' in task['error']
    assert store.claim() is None


def test_validation_and_json_logging(store,workspace):
    pid=store.project('Sample','Build useful software',workspace)
    with pytest.raises(ValueError):store.task(pid,'x','spec',[])
    with pytest.raises(ValueError):store.task(pid,'x','spec',[[]])
    with pytest.raises(ValueError):store.task(pid,'x','spec',[['echo','x']],['missing'])
    store.event(None,'Controller','started',safe=True)
    assert json.loads((store.home/'events.jsonl').read_text())['data']['safe']


def test_retry_not_claimed_early(store,workspace):
    pid=store.project('Sample','Build useful software',workspace)
    tid=store.task(pid,'Task','Implement useful feature',[['python','-V']])
    store.update(tid,status='retry',available=time.time()+60)
    assert store.claim() is None
