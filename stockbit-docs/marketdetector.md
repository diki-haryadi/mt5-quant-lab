curl 'https://exodus.stockbit.com/marketdetectors/TPIA?transaction_type=TRANSACTION_TYPE_NET&market_board=MARKET_BOARD_REGULER&investor_type=INVESTOR_TYPE_ALL&limit=25&period=BROKER_SUMMARY_PERIOD_LATEST' \
  -H 'accept: application/json' \
  -H 'accept-language: en-US,en;q=0.9' \
  -H 'authorization: Bearer eyJhbGciOiJSUzI1NiIsImtpZCI6ImExNWQ5OGE2LTdkYzgtNDM3NS05NDk0LTEyOWJlM2RlODVkNCIsInR5cCI6IkpXVCJ9.eyJkYXRhIjp7InVzZSI6ImRpa2loYXJ5YWRpIiwiZW1hIjoiZGlraS5oYXJ5YWRpMTkwMkBnbWFpbC5jb20iLCJmdWwiOiJiZW4iLCJzZXMiOiJlSnMydHo0bzZPYXhRZzFBIiwiZHZjIjoiMDRiYmU4MDlhZmI0MTFhMWUxOGY2N2UzMmVlMzI2MTQiLCJ1aWQiOjE1MTg3OTksImNvdSI6IlNHIn0sImV4cCI6MTc4MDc2MTY4NSwiaWF0IjoxNzgwNjc1Mjg1LCJpc3MiOiJTVE9DS0JJVCIsImp0aSI6IjEyNjM2ZDExLWE4OGQtNDU5ZC04NTFkLWQxMDliMTEwMDhmMiIsIm5iZiI6MTc4MDY3NTI4NSwidmVyIjoidjEifQ.mGEEsoLmsK-NvL9JCq6yAeLk4n9wcc25VOZVUOxl0_K01RCrSPFxmSe9sZqR0WUbdlo3QIA3vh-RC6Z00AQuj9gffNhf5yPEHzUesx4Dh3ST5qdVnXLxaCex8vxrvlsDWu3RDfJ3Y3UqN2OgylDfOD4It7hUHeL2iNCmPdSRJyjLWR7zYI6vcP0qPvLgMfXmvb51KPKDCPvAh7yaBLt8miz5h2uP9eMDqduU98rs0Exhsnf3jAyxtCDQRR4cao5Kgxt7xjwIf-aUf07JP2BOaXBAUPyJ2EA503vPrgcXKMS26FCwrc_crEnUnAGH1bS2x4-fr6IS-KtvEMOGugUlYg' \
  -H 'origin: https://stockbit.com' \
  -H 'priority: u=1, i' \
  -H 'referer: https://stockbit.com/' \
  -H 'sec-ch-ua: "Brave";v="147", "Not.A/Brand";v="8", "Chromium";v="147"' \
  -H 'sec-ch-ua-mobile: ?0' \
  -H 'sec-ch-ua-platform: "macOS"' \
  -H 'sec-fetch-dest: empty' \
  -H 'sec-fetch-mode: cors' \
  -H 'sec-fetch-site: same-site' \
  -H 'sec-gpc: 1' \
  -H 'user-agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36'
{
    "message": "Successfully retrieved market detector data",
    "data": {
        "bandar_detector": {
            "average": 1382.1521,
            "avg": {
                "accdist": "Big Dist",
                "amount": -1065434700000,
                "percent": -61.120285,
                "vol": -7708520
            },
            "avg5": {
                "accdist": "Big Dist",
                "amount": -1159651500000,
                "percent": -66.52518,
                "vol": -8390188
            },
            "broker_accdist": "Dist",
            "number_broker_buysell": 43,
            "top1": {
                "accdist": "Big Dist",
                "amount": -1451387500000,
                "percent": -83.26106,
                "vol": -10500925
            },
            "top3": {
                "accdist": "Big Dist",
                "amount": -1124637000000,
                "percent": -64.51652,
                "vol": -8136854
            },
            "top5": {
                "accdist": "Big Dist",
                "amount": -912015560000,
                "percent": -52.319164,
                "vol": -6598518
            },
            "top10": {
                "accdist": "Big Dist",
                "amount": -455036100000,
                "percent": -26.103842,
                "vol": -3292229
            },
            "total_buyer": 62,
            "total_seller": 19,
            "value": 1743176900000,
            "volume": 12612048
        },
        "broker_summary": {
            "brokers_buy": [
                {
                    "blot": "1.623245e+06",
                    "blotv": "1.837146e+08",
                    "bval": "2.33064954e+11",
                    "bvalv": "2.66081781e+11",
                    "netbs_broker_code": "ZP",
                    "netbs_buy_avg_price": "1448.343142025729",
                    "netbs_date": "20260605",
                    "netbs_stock_code": "TPIA",
                    "type": "Asing",
                    "freq": "10802"
                },
                {
                    "blot": "1.441981e+06",
                    "blotv": "1.441981e+08",
                    "bval": "1.89861285e+11",
                    "bvalv": "1.89861285e+11",
                    "netbs_broker_code": "DP",
                    "netbs_buy_avg_price": "1316.6698104898746",
                    "netbs_date": "20260605",
                    "netbs_stock_code": "TPIA",
                    "type": "Asing",
                    "freq": "2267"
                },
                {
                    "blot": "1.314481e+06",
                    "blotv": "1.618834e+08",
                    "bval": "1.79972876e+11",
                    "bvalv": "2.272116485e+11",
                    "netbs_broker_code": "LG",
                    "netbs_buy_avg_price": "1403.5512504679293",
                    "netbs_date": "20260605",
                    "netbs_stock_code": "TPIA",
                    "type": "Lokal",
                    "freq": "3545"
                },
                {
                    "blot": "862560",
                    "blotv": "1.025229e+08",
                    "bval": "1.283168155e+11",
                    "bvalv": "1.519168085e+11",
                    "netbs_broker_code": "BK",
                    "netbs_buy_avg_price": "1481.7841526137088",
                    "netbs_date": "20260605",
                    "netbs_stock_code": "TPIA",
                    "type": "Asing",
                    "freq": "4216"
                },
                {
                    "blot": "750513",
                    "blotv": "7.53513e+07",
                    "bval": "1.130959425e+11",
                    "bvalv": "1.135599425e+11",
                    "netbs_broker_code": "BB",
                    "netbs_buy_avg_price": "1507.0734346985387",
                    "netbs_date": "20260605",
                    "netbs_stock_code": "TPIA",
                    "type": "Lokal",
                    "freq": "3768"
                },
                {
                    "blot": "777771",
                    "blotv": "9.21283e+07",
                    "bval": "1.104239235e+11",
                    "bvalv": "1.32298529e+11",
                    "netbs_broker_code": "OD",
                    "netbs_buy_avg_price": "1436.0248588110276",
                    "netbs_date": "20260605",
                    "netbs_stock_code": "TPIA",
                    "type": "Pemerintah",
                    "freq": "5966"
                },
                {
                    "blot": "761276",
                    "blotv": "2.68528e+08",
                    "bval": "9.88933175e+10",
                    "bvalv": "3.82147413e+11",
                    "netbs_broker_code": "YP",
                    "netbs_buy_avg_price": "1423.1194251623667",
                    "netbs_date": "20260605",
                    "netbs_stock_code": "TPIA",
                    "type": "Asing",
                    "freq": "20263"
                },
                {
                    "blot": "656631",
                    "blotv": "1.667992e+08",
                    "bval": "9.18346615e+10",
                    "bvalv": "2.467962085e+11",
                    "netbs_broker_code": "AZ",
                    "netbs_buy_avg_price": "1479.600672545192",
                    "netbs_date": "20260605",
                    "netbs_stock_code": "TPIA",
                    "type": "Lokal",
                    "freq": "4836"
                },
                {
                    "blot": "563494",
                    "blotv": "1.404966e+08",
                    "bval": "8.4641444e+10",
                    "bvalv": "2.12500716e+11",
                    "netbs_broker_code": "PD",
                    "netbs_buy_avg_price": "1512.4972134556992",
                    "netbs_date": "20260605",
                    "netbs_stock_code": "TPIA",
                    "type": "Lokal",
                    "freq": "21946"
                },
                {
                    "blot": "564168",
                    "blotv": "3.152726e+08",
                    "bval": "7.6317557e+10",
                    "bvalv": "4.613096035e+11",
                    "netbs_broker_code": "CC",
                    "netbs_buy_avg_price": "1463.2086756032716",
                    "netbs_date": "20260605",
                    "netbs_stock_code": "TPIA",
                    "type": "Pemerintah",
                    "freq": "22834"
                },
                {
                    "blot": "402106",
                    "blotv": "4.125697e+08",
                    "bval": "6.9988258e+10",
                    "bvalv": "6.05037678e+11",
                    "netbs_broker_code": "MG",
                    "netbs_buy_avg_price": "1466.5102114866895",
                    "netbs_date": "20260605",
                    "netbs_stock_code": "TPIA",
                    "type": "Lokal",
                    "freq": "11689"
                },
                {
                    "blot": "457220",
                    "blotv": "5.13305e+07",
                    "bval": "6.02552645e+10",
                    "bvalv": "6.8723196e+10",
                    "netbs_broker_code": "HP",
                    "netbs_buy_avg_price": "1338.837455314092",
                    "netbs_date": "20260605",
                    "netbs_stock_code": "TPIA",
                    "type": "Lokal",
                    "freq": "1083"
                },
                {
                    "blot": "396161",
                    "blotv": "6.5988e+07",
                    "bval": "5.77351875e+10",
                    "bvalv": "9.7478268e+10",
                    "netbs_broker_code": "NI",
                    "netbs_buy_avg_price": "1477.212038552464",
                    "netbs_date": "20260605",
                    "netbs_stock_code": "TPIA",
                    "type": "Pemerintah",
                    "freq": "4556"
                },
                {
                    "blot": "241546",
                    "blotv": "5.61844e+07",
                    "bval": "2.9036234e+10",
                    "bvalv": "7.8475167e+10",
                    "netbs_broker_code": "RF",
                    "netbs_buy_avg_price": "1396.7429927168396",
                    "netbs_date": "20260605",
                    "netbs_stock_code": "TPIA",
                    "type": "Lokal",
                    "freq": "468"
                },
                {
                    "blot": "202150",
                    "blotv": "5.076e+07",
                    "bval": "2.3828078e+10",
                    "bvalv": "7.05678055e+10",
                    "netbs_broker_code": "SS",
                    "netbs_buy_avg_price": "1390.22469464145",
                    "netbs_date": "20260605",
                    "netbs_stock_code": "TPIA",
                    "type": "Lokal",
                    "freq": "737"
                },
                {
                    "blot": "155001",
                    "blotv": "2.79933e+07",
                    "bval": "2.1624524e+10",
                    "bvalv": "4.16776555e+10",
                    "netbs_broker_code": "AI",
                    "netbs_buy_avg_price": "1488.8439555179275",
                    "netbs_date": "20260605",
                    "netbs_stock_code": "TPIA",
                    "type": "Asing",
                    "freq": "961"
                },
                {
                    "blot": "106390",
                    "blotv": "1.702999e+08",
                    "bval": "2.14607285e+10",
                    "bvalv": "2.57415453e+11",
                    "netbs_broker_code": "AK",
                    "netbs_buy_avg_price": "1511.542009126253",
                    "netbs_date": "20260605",
                    "netbs_stock_code": "TPIA",
                    "type": "Asing",
                    "freq": "8169"
                },
                {
                    "blot": "161115",
                    "blotv": "3.02274e+07",
                    "bval": "2.0823858e+10",
                    "bvalv": "4.2356671e+10",
                    "netbs_broker_code": "YJ",
                    "netbs_buy_avg_price": "1401.267426242416",
                    "netbs_date": "20260605",
                    "netbs_stock_code": "TPIA",
                    "type": "Lokal",
                    "freq": "835"
                },
                {
                    "blot": "109940",
                    "blotv": "2.9705e+07",
                    "bval": "1.6301546e+10",
                    "bvalv": "4.4480531e+10",
                    "netbs_broker_code": "DR",
                    "netbs_buy_avg_price": "1497.4088873926949",
                    "netbs_date": "20260605",
                    "netbs_stock_code": "TPIA",
                    "type": "Asing",
                    "freq": "1940"
                },
                {
                    "blot": "225589",
                    "blotv": "3.607039e+08",
                    "bval": "1.44241045e+10",
                    "bvalv": "5.229578255e+11",
                    "netbs_broker_code": "XL",
                    "netbs_buy_avg_price": "1449.8258141927492",
                    "netbs_date": "20260605",
                    "netbs_stock_code": "TPIA",
                    "type": "Lokal",
                    "freq": "76175"
                },
                {
                    "blot": "80905",
                    "blotv": "1.28307e+07",
                    "bval": "1.1665747e+10",
                    "bvalv": "1.8787295e+10",
                    "netbs_broker_code": "IF",
                    "netbs_buy_avg_price": "1464.2455205094031",
                    "netbs_date": "20260605",
                    "netbs_stock_code": "TPIA",
                    "type": "Lokal",
                    "freq": "660"
                },
                {
                    "blot": "85077",
                    "blotv": "5.83298e+07",
                    "bval": "1.05485495e+10",
                    "bvalv": "8.30323655e+10",
                    "netbs_broker_code": "KK",
                    "netbs_buy_avg_price": "1423.4982033197439",
                    "netbs_date": "20260605",
                    "netbs_stock_code": "TPIA",
                    "type": "Asing",
                    "freq": "4088"
                },
                {
                    "blot": "90051",
                    "blotv": "1.0117e+08",
                    "bval": "1.04497415e+10",
                    "bvalv": "1.44920467e+11",
                    "netbs_broker_code": "CP",
                    "netbs_buy_avg_price": "1432.445062765642",
                    "netbs_date": "20260605",
                    "netbs_stock_code": "TPIA",
                    "type": "Asing",
                    "freq": "4886"
                },
                {
                    "blot": "75123",
                    "blotv": "7.5123e+06",
                    "bval": "1.04313265e+10",
                    "bvalv": "1.04313265e+10",
                    "netbs_broker_code": "RX",
                    "netbs_buy_avg_price": "1388.566284626546",
                    "netbs_date": "20260605",
                    "netbs_stock_code": "TPIA",
                    "type": "Asing",
                    "freq": "195"
                },
                {
                    "blot": "70622",
                    "blotv": "1.94855e+07",
                    "bval": "9.49847e+09",
                    "bvalv": "2.83961845e+10",
                    "netbs_broker_code": "YB",
                    "netbs_buy_avg_price": "1457.298221754638",
                    "netbs_date": "20260605",
                    "netbs_stock_code": "TPIA",
                    "type": "Lokal",
                    "freq": "1672"
                }
            ],
            "brokers_sell": [
                {
                    "netbs_broker_code": "YU",
                    "netbs_date": "20260605",
                    "netbs_sell_avg_price": "1383.1233736599336",
                    "netbs_stock_code": "TPIA",
                    "slot": "-1.212417e+07",
                    "slotv": "1.3793625e+09",
                    "sval": "-1.664784808e+12",
                    "svalv": "1.9078285145e+12",
                    "type": "Asing",
                    "freq": "61500"
                },
                {
                    "netbs_broker_code": "TP",
                    "netbs_date": "20260605",
                    "netbs_sell_avg_price": "1434.4481529061745",
                    "netbs_stock_code": "TPIA",
                    "slot": "-328026",
                    "slotv": "1.071873e+08",
                    "sval": "-4.3725857e+10",
                    "svalv": "1.537546245e+11",
                    "type": "Asing",
                    "freq": "4867"
                },
                {
                    "netbs_broker_code": "SQ",
                    "netbs_date": "20260605",
                    "netbs_sell_avg_price": "1527.4107826996537",
                    "netbs_stock_code": "TPIA",
                    "slot": "-64365",
                    "slotv": "7.11269e+07",
                    "sval": "-1.5888417e+10",
                    "svalv": "1.08639994e+11",
                    "type": "Lokal",
                    "freq": "4711"
                },
                {
                    "netbs_broker_code": "PO",
                    "netbs_date": "20260605",
                    "netbs_sell_avg_price": "1585.1619493809112",
                    "netbs_stock_code": "TPIA",
                    "slot": "-53377",
                    "slotv": "5.6777e+06",
                    "sval": "-8.502674e+09",
                    "svalv": "9.000074e+09",
                    "type": "Lokal",
                    "freq": "174"
                },
                {
                    "netbs_broker_code": "SH",
                    "netbs_date": "20260605",
                    "netbs_sell_avg_price": "1652.9882859835734",
                    "netbs_stock_code": "TPIA",
                    "slot": "-21360",
                    "slotv": "3.7135e+06",
                    "sval": "-3.9769895e+09",
                    "svalv": "6.138372e+09",
                    "type": "Lokal",
                    "freq": "228"
                },
                {
                    "netbs_broker_code": "EL",
                    "netbs_date": "20260605",
                    "netbs_sell_avg_price": "1551.2252771618626",
                    "netbs_stock_code": "TPIA",
                    "slot": "-10050",
                    "slotv": "2.255e+06",
                    "sval": "-1.860863e+09",
                    "svalv": "3.498013e+09",
                    "type": "Lokal",
                    "freq": "71"
                },
                {
                    "netbs_broker_code": "AO",
                    "netbs_date": "20260605",
                    "netbs_sell_avg_price": "1511.9251506268138",
                    "netbs_stock_code": "TPIA",
                    "slot": "-6571",
                    "slotv": "1.35766e+07",
                    "sval": "-1.7331785e+09",
                    "svalv": "2.0526803e+10",
                    "type": "Lokal",
                    "freq": "703"
                },
                {
                    "netbs_broker_code": "XA",
                    "netbs_date": "20260605",
                    "netbs_sell_avg_price": "1523.5940101697192",
                    "netbs_stock_code": "TPIA",
                    "slot": "3472",
                    "slotv": "2.67854e+07",
                    "sval": "-1.303309e+09",
                    "svalv": "4.0810075e+10",
                    "type": "Asing",
                    "freq": "1789"
                },
                {
                    "netbs_broker_code": "RO",
                    "netbs_date": "20260605",
                    "netbs_sell_avg_price": "1439.0575849822426",
                    "netbs_stock_code": "TPIA",
                    "slot": "-2151",
                    "slotv": "1.1826e+06",
                    "sval": "-2.970325e+08",
                    "svalv": "1.7018295e+09",
                    "type": "Lokal",
                    "freq": "143"
                },
                {
                    "netbs_broker_code": "GA",
                    "netbs_date": "20260605",
                    "netbs_sell_avg_price": "1553.3333333333333",
                    "netbs_stock_code": "TPIA",
                    "slot": "-1751",
                    "slotv": "750000",
                    "sval": "-2.862585e+08",
                    "svalv": "1.165e+09",
                    "type": "Lokal",
                    "freq": "27"
                },
                {
                    "netbs_broker_code": "FZ",
                    "netbs_date": "20260605",
                    "netbs_sell_avg_price": "1432.5926846443808",
                    "netbs_stock_code": "TPIA",
                    "slot": "-363",
                    "slotv": "2.4141e+06",
                    "sval": "-2.39639e+08",
                    "svalv": "3.458422e+09",
                    "type": "Lokal",
                    "freq": "197"
                },
                {
                    "netbs_broker_code": "MU",
                    "netbs_date": "20260605",
                    "netbs_sell_avg_price": "1627.8223495702007",
                    "netbs_stock_code": "TPIA",
                    "slot": "-1146",
                    "slotv": "139600",
                    "sval": "-1.89784e+08",
                    "svalv": "2.27244e+08",
                    "type": "Lokal",
                    "freq": "28"
                },
                {
                    "netbs_broker_code": "SA",
                    "netbs_date": "20260605",
                    "netbs_sell_avg_price": "1517.5",
                    "netbs_stock_code": "TPIA",
                    "slot": "-1000",
                    "slotv": "200000",
                    "sval": "-1.74e+08",
                    "svalv": "3.035e+08",
                    "type": "Lokal",
                    "freq": "2"
                },
                {
                    "netbs_broker_code": "QA",
                    "netbs_date": "20260605",
                    "netbs_sell_avg_price": "1427.8196297890659",
                    "netbs_stock_code": "TPIA",
                    "slot": "-906",
                    "slotv": "232300",
                    "sval": "-1.451705e+08",
                    "svalv": "3.316825e+08",
                    "type": "Lokal",
                    "freq": "54"
                },
                {
                    "netbs_broker_code": "ID",
                    "netbs_date": "20260605",
                    "netbs_sell_avg_price": "1523.938775510204",
                    "netbs_stock_code": "TPIA",
                    "slot": "-110",
                    "slotv": "122500",
                    "sval": "-3.20525e+07",
                    "svalv": "1.866825e+08",
                    "type": "Lokal",
                    "freq": "37"
                },
                {
                    "netbs_broker_code": "TF",
                    "netbs_date": "20260605",
                    "netbs_sell_avg_price": "1650.3206997084549",
                    "netbs_stock_code": "TPIA",
                    "slot": "-101",
                    "slotv": "34300",
                    "sval": "-2.4546e+07",
                    "svalv": "5.6606e+07",
                    "type": "Lokal",
                    "freq": "8"
                },
                {
                    "netbs_broker_code": "PF",
                    "netbs_date": "20260605",
                    "netbs_sell_avg_price": "1562.8977272727273",
                    "netbs_stock_code": "TPIA",
                    "slot": "-53",
                    "slotv": "8800",
                    "sval": "-8.851e+06",
                    "svalv": "1.37535e+07",
                    "type": "Lokal",
                    "freq": "9"
                },
                {
                    "netbs_broker_code": "GI",
                    "netbs_date": "20260605",
                    "netbs_sell_avg_price": "1695",
                    "netbs_stock_code": "TPIA",
                    "slot": "-20",
                    "slotv": "2000",
                    "sval": "-3.39e+06",
                    "svalv": "3.39e+06",
                    "type": "Asing",
                    "freq": "1"
                },
                {
                    "netbs_broker_code": "IT",
                    "netbs_date": "20260605",
                    "netbs_sell_avg_price": "1350",
                    "netbs_stock_code": "TPIA",
                    "slot": "0",
                    "slotv": "500",
                    "sval": "-25000",
                    "svalv": "675000",
                    "type": "Lokal",
                    "freq": "1"
                }
            ],
            "symbol": "TPIA"
        },
        "from": "2026-06-05",
        "to": "2026-06-05"
    }
}

                         Field respons                         │                Komponen di chart                │                 Bukti angka                  │
  ├───────────────────────────────────────────────────────────────┼─────────────────────────────────────────────────┼──────────────────────────────────────────────┤
  │ price_chart_data (275 titik, per-menit 09:00→16:xx)           │ 🔵 garis Price (axis kanan)                     │ value.raw "1560" → axis kanan 1,174–1,782 ✅ │
  ├───────────────────────────────────────────────────────────────┼─────────────────────────────────────────────────┼──────────────────────────────────────────────┤
  │ broker_chart_data (per broker, per-menit, bertanda ±)         │ 🟢 Net Buy / 🔴 Net Sell (axis kiri)            │ formatted "(24.5B)" → axis kiri ±129.7B ✅   │
  ├───────────────────────────────────────────────────────────────┼─────────────────────────────────────────────────┼──────────────────────────────────────────────┤
  │ broker_chart_data[].type = TYPE_CHART_VALUE (+ varian volume) │ dua ikon toggle kanan-atas (nilai Rp vs volume) │ ✅        