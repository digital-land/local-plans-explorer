## Local plans explorer


#### Prerequisites

1. python 3

Create a virtualenv and activate it, and then:

    make init

Run the app

    flask run

and have a look at http://localhost:5000


#### Loading baseline data into the database

There are commands for loading organsations, plans and boundaries that can be run as follows

    flask data load-orgs
    flask data load-plans
    flask data load-boundaries

Organisations would need to be loaded before either loading plans or boundaries.

Once at least organastions and plans are loaded then documents can be loaded.

The [local-plan-document.csv](data/local-plan-document.csv) is reasonably large so loading it is easiest done with posgres \COPY command.

That file needs a bit of preprocessing to make it \COPY command friendly.

To do that run this command:

    flask data create-import-docs

That generates a preprocessed file named local-plan-document-copyable.csv in the data directory.

To run the \COPY command, and assuming you are in the data directory, open a psql shell and run:

    \COPY local_plan_document(reference,local_plan,name,document_url,documentation_url,document_types,start_date,end_date,description,status) FROM 'local-plan-document-copyable.csv' WITH CSV HEADER;
