# QuantIAN
QuantIAN is a multi-cloud Intelligent Autonomous Network (IAN) for quantitative 
market analytics. The system operates over a decentralized P2P infrastructure 
and is composed of three specialized nodes, each hosted on a different cloud 
provider, that work together to process live market data, detect anomalies, and 
evaluate portfolio risk.

## Architecture

| Component                       | Cloud | Service                                      |
|---------------------------------|-------|----------------------------------------------|
| Real-Time Market Data Ingestion | AWS   | Kinesis + Lambda                             |
| AI-Driven Anomaly Detection     | Azure | Anomaly Detector + Event Hub                 |
| Portfolio Risk Analysis         | GCP   | BigQuery + Cloud Functions + Cloud Scheduler |

## Key Features

- Real-time market data ingestion from public exchange APIs
- ML-based anomaly detection with human-in-the-loop review dashboard
- Automated portfolio risk metric computation (volatility, VaR, drawdown)
- Decentralized P2P messaging layer connecting all three cloud nodes
- Semi-autonomous design — AI flags events, humans validate them

### Repo Sturcutre
```
quantian/
├── aws-ingestion/
│   ├── kinesis/
│   ├── lambda/
│   └── README.md
├── azure-anomaly/
│   ├── anomaly-detector/
│   ├── dashboard/
│   └── README.md
├── gcp-risk/
│   ├── cloud-functions/
│   ├── bigquery/
│   ├── scheduler/
│   └── README.md
├── p2p-network/
│   ├── node-config/
│   └── README.md
├── docs/
│   └── architecture-diagrams/
├── .gitignore
└── README.md
```