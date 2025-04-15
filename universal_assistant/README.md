Hey I am building this project

Universal Assistant via MCP

In this project, you will implement a LLM based assistant (a text version of Siri). You will be

implementing a set of tools and protocols so that your system is easily extensible. Here are

the major functonalities.

• You will develop a system that allows the customer to invoke various tools.

• Each of these tools has to be based on MCP which is the dominant paradigm by which

you provide new capabiliVes to LLMs (see

h\ps://modelcontextprotocol.io/introduction )

• You will incorporate 3 sample servers (from

h\ps://modelcontextprotocol.io/examples)

• You will implement 3 custom servers (math server that can

add/subtract/muliply/divide; weather server that takes a city and randomly returns

some weather; process server that uses psutil to get details about the machine).

Technical Requirements

• Each of the analysis has to be implemented using Prefect/DBOS workflows

• You have to do copious AND ORGANIZED logging using MLFlow

• At least couple of the services has to be docker based. For example, you can have a

docker service running on a port that takes a PDF as input and produces an array of

transactions as output. It is up-to-you to decide which services are docker based.

Please me complete my project