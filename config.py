config = {
    'username': 'agent@rec.foi.hr',
    'password': 'tajna',
    'psql': {
        'engine': {
            'path': 'psql',
            'args': '-d sparp -U korisnik -p lozinka'
        },
        'expectedValues': [
            'sparp=#',
            'ERROR:.*\r\n'
        ]
    },
    'mongo': {
        'engine': {
            'path': 'mongo',
            'args': ''
        },
        'expectedValues': [
            '> ',
            'E QUERY.*\r\n'
        ]
    },
    'neo4j': {
        'engine': {
            'path': 'cypher-shell',
            'args': '-u korisnik -p lozinka'
        },
        'expectedValues': [
            'neo4j> ',
            'E QUERY.*\r\n'
        ]
    },
}
