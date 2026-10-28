import pytest
from engineering_os.plans import import_plan


def test_plan_dependencies_and_validation(store,workspace):
    task={'key':'first','title':'Feature','spec':'Implement feature behavior','checks':[['python','-V']]}
    plan={'name':'Project','brief':'Build a useful product','tasks':[task,{**task,'key':'next','dependencies':['first']}]}
    pid=import_plan(store,plan,workspace)
    tasks=store.snapshot()['tasks']
    assert tasks[1]['dependencies']==[tasks[0]['id']]


def test_invalid_plan_does_not_partially_import(store,workspace):
    plan={'name':'Project','brief':'Build a useful product','tasks':[{'key':'x','title':'x','spec':'Implement feature behavior','checks':[['python','-V']],'dependencies':['future']}]}
    with pytest.raises(ValueError):import_plan(store,plan,workspace)
    assert store.snapshot()['projects']==[]
