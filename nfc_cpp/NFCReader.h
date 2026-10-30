#pragma once
#include <string>
#include <vector>
#ifdef _WIN32
#include <windows.h>
#include <winscard.h>
#else
#include <PCSC/winscard.h>
#include <PCSC/wintypes.h>
#endif

// This adapter intentionally supports only ACS-compatible Type 2 memory APDUs.
// It does not treat the hardware UID as an authentication credential.
class NFCReader {
public:
    NFCReader();
    ~NFCReader();
    NFCReader(const NFCReader&) = delete;
    NFCReader& operator=(const NFCReader&) = delete;
    void connect();
    std::string readToken();
    void writeToken(const std::string& token);
private:
    SCARDCONTEXT context_ = 0;
    SCARDHANDLE card_ = 0;
    DWORD protocol_ = 0;
    std::vector<unsigned char> transmit(const std::vector<unsigned char>& command);
    std::vector<unsigned char> readPages(unsigned char start);
    void verifyType2();
    void writePage(unsigned char page, const unsigned char* bytes);
};
