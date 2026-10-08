## Local plans explorer
![build](https://github.com//digital-land/local-plans-explorer/actions/workflows/ci.yml/badge.svg)

#### Prerequisites

1. Python 3.13 (see [.python-version](.python-version))
2. Node 24 LTS (see [.nvmrc](.nvmrc))

Create a virtualenv and activate it, and then:

    make init

This installs Python and npm dependencies and builds the frontend assets into `application/static`. These are not committed; rebuild them after changing anything in `src/` with:

    npm run build

Run the app

    flask run

and have a look at http://localhost:5000

If you click around the app you will get errors until you have set up the database. Steps below.

#### Loading baseline data into the database

Create a Postgres db called local_plans

    createdb local_plans

Run migrations

    flask db upgrade

There is a command for loading organsations, plans, boundaries and document types, that can be run as follows

    flask data load-all

The [local-plan-document.csv](data/local-plan-document.csv) is reasonably large so loading it is easiest done with posgres \COPY command.

That file has had a bit of preprocessing to make it \COPY command friendly. That is the [local-plan-document-copyable.csv](data/local-plan-document-copyable.csv)

To load the documents run the \COPY command, and assuming you are in the data directory, open a psql shell connecting to the local_plans database:

    psql -d local_plans

Then run \COPY command:

    \COPY local_plan_document(reference,local_plan,name,document_url,documentation_url,document_types,start_date,end_date,description,status) FROM 'local-plan-document-copyable.csv' WITH CSV HEADER;
