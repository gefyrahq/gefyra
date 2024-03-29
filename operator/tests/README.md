# Gefyra Operator Tests

## Run the test suite
From `gefyra/operator/`

1. enter a poetry shell: `poetry shell`
2. install all dependencies: `poetry install`
3. run all tests: `poetry run pytest `

## Options

### Only unit / integration tests
* run only unit tests: `poetry run pytest tests/unit/`  
* run only integration tests: `poetry run pytest tests/integration/`  

### Coverage
Create a coverage report with:  
1. run all tests: `poetry run coverage run -m pytest`
2. create a html report: `poetry run coverage html` or others options


## Useful commands for manual testing
Create a Gefyra client ("client-a"):  
`kubectl -n gefyra apply -f tests/fixtures/a_gefyra_client.yaml`

Patch the Stowaway config (client to enter ACTIVE state):  
`kubectl -n gefyra patch gefyraclient client-a --type='merge' -p '{"providerParameter": {"subnet": "192.168.101.0/24"}}'`

Patch the Stowaway config (client to return to WAITING state):  
`kubectl -n gefyra patch gefyraclient client-a --type='merge' -p '{"providerParameter": null}'`

Delete the Gefyra client ("client-a"):  
`kubectl -n gefyra delete gefyraclient client-a`
