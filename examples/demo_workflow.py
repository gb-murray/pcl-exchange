from pcl_exchange.builder import PCLMessageBuilder

# intialize the builder
builder = PCLMessageBuilder(                    
    sender_id="https://ror.org/03yrm5c26",
    receiver_id="https://ror.org/01bj3aw27"
)

# set a payload
builder.set_content(
    instrument="urn:aimd:instrument:proto-xrd-01",
    sample="igsn:XYZ12345",
    method="urn:aimd:method:xrd:powder:theta-2theta:v1",
    params={
        "scan_range": {"val": "10 90", "unit": "deg 2theta"},
        "step": {"val": 0.02, "unit": "deg"}
    }
)

# add envelope metadata
builder.add_capability("xrd.powder.theta-2theta")

# sign and build
builder.sign(private_key_pem=b"...") 
message = builder.build()

# output as JSON-LD
print(message.to_json())