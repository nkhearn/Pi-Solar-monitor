import os
import subprocess
import socket

CERT_DIR = "certs"
CA_KEY = os.path.join(CERT_DIR, "ca.key")
CA_CRT = os.path.join(CERT_DIR, "ca.crt")
SERVER_KEY = os.path.join(CERT_DIR, "server.key")
SERVER_CRT = os.path.join(CERT_DIR, "server.crt")
SERVER_CSR = os.path.join(CERT_DIR, "server.csr")
EXT_FILE = os.path.join(CERT_DIR, "server.ext")

def get_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # doesn't even have to be reachable
        s.connect(('10.255.255.255', 1))
        IP = s.getsockname()[0]
    except Exception:
        IP = '127.0.0.1'
    finally:
        s.close()
    return IP

def generate_certificates():
    if not os.path.exists(CERT_DIR):
        os.makedirs(CERT_DIR)

    # 1. Generate CA key and certificate
    if not os.path.exists(CA_KEY) or not os.path.exists(CA_CRT):
        print("Generating CA certificate...")
        subprocess.run([
            "openssl", "genrsa", "-out", CA_KEY, "4096"
        ], check=True)
        subprocess.run([
            "openssl", "req", "-x509", "-new", "-nodes", "-key", CA_KEY,
            "-sha256", "-days", "3650", "-out", CA_CRT,
            "-subj", "/C=US/ST=Solar/L=Solar/O=PiSolar/CN=PiSolarCA"
        ], check=True)

    # 2. Generate Server key and CSR
    if not os.path.exists(SERVER_KEY) or not os.path.exists(SERVER_CRT):
        print("Generating Server certificate...")
        subprocess.run([
            "openssl", "genrsa", "-out", SERVER_KEY, "2048"
        ], check=True)

        ip_addr = get_ip()
        hostname = socket.gethostname()

        with open(EXT_FILE, "w") as f:
            f.write(f"""authorityKeyIdentifier=keyid,issuer
basicConstraints=CA:FALSE
keyUsage = digitalSignature, nonRepudiation, keyEncipherment, dataEncipherment
subjectAltName = @alt_names

[alt_names]
DNS.1 = {hostname}
DNS.2 = localhost
IP.1 = {ip_addr}
IP.2 = 127.0.0.1
""")

        subprocess.run([
            "openssl", "req", "-new", "-key", SERVER_KEY, "-out", SERVER_CSR,
            "-subj", f"/C=US/ST=Solar/L=Solar/O=PiSolar/CN={hostname}"
        ], check=True)

        subprocess.run([
            "openssl", "x509", "-req", "-in", SERVER_CSR, "-CA", CA_CRT,
            "-CAkey", CA_KEY, "-CAcreateserial", "-out", SERVER_CRT,
            "-days", "825", "-sha256", "-extfile", EXT_FILE
        ], check=True)

if __name__ == "__main__":
    generate_certificates()
