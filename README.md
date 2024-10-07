## Local plans explorer


#### Prerequisites

1. python 3

Create a virtualenv and activate it, and then:

    make init

Run the app

    flask run

and have a look at http://localhost:5000


#### Loading baseline data into the database

Create a Postgres db called local_plans

    createdb local_plans

There is a command for loading organsations, plans, boundaries and document types, that can be run as follows

    flask data load-all

The [local-plan-document.csv](data/local-plan-document.csv) is reasonably large so loading it is easiest done with posgres \COPY command.

That file has had a bit of preprocessing to make it \COPY command friendly. That is the [local-plan-document-copyable.csv](data/local-plan-document-copyable.csv)

To load the documents run the \COPY command, and assuming you are in the data directory, open a psql shell and run:

    psql -d local_plans

Then run \COPY command:

    \COPY local_plan_document(reference,local_plan,name,document_url,documentation_url,document_types,start_date,end_date,description,status) FROM 'local-plan-document-copyable.csv' WITH CSV HEADER;
