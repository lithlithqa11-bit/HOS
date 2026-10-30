#include "NFCReader.h"
#include <algorithm>
#include <stdexcept>
#include <cctype>

namespace {
constexpr unsigned char MAGIC[4] = {'M', 'L', 'N', '1'};
int hexNibble(char c) {
    if (c >= '0' && c <= '9') return c - '0';
    if (c >= 'a' && c <= 'f') return c - 'a' + 10;
    throw std::runtime_error("invalid_token");
}
}

NFCReader::NFCReader() {
    if (SCardEstablishContext(SCARD_SCOPE_USER, nullptr, nullptr, &context_) != SCARD_S_SUCCESS)
        throw std::runtime_error("pcsc_service_unavailable");
}

NFCReader::~NFCReader() {
    if (card_) SCardDisconnect(card_, SCARD_LEAVE_CARD);
    if (context_) SCardReleaseContext(context_);
}

void NFCReader::connect() {
    DWORD size = 0;
#ifdef _WIN32
    LONG result = SCardListReadersA(context_, nullptr, nullptr, &size);
#else
    LONG result = SCardListReaders(context_, nullptr, nullptr, &size);
#endif
    if (result != SCARD_S_SUCCESS || size < 2) throw std::runtime_error("no_reader");
    std::vector<char> readers(size);
#ifdef _WIN32
    result = SCardListReadersA(context_, nullptr, readers.data(), &size);
#else
    result = SCardListReaders(context_, nullptr, readers.data(), &size);
#endif
    if (result != SCARD_S_SUCCESS) throw std::runtime_error("reader_list_failed");
    // Try each reader: combined contact/contactless devices expose several slots.
    for (const char* name = readers.data(); *name; name += std::char_traits<char>::length(name) + 1) {
#ifdef _WIN32
        result = SCardConnectA(context_, name, SCARD_SHARE_SHARED, SCARD_PROTOCOL_T0 | SCARD_PROTOCOL_T1,
                              &card_, &protocol_);
#else
        result = SCardConnect(context_, name, SCARD_SHARE_SHARED, SCARD_PROTOCOL_T0 | SCARD_PROTOCOL_T1,
                             &card_, &protocol_);
#endif
        if (result == SCARD_S_SUCCESS) return;
        card_ = 0;
    }
    throw std::runtime_error("no_card_or_reader_busy");
}

std::vector<unsigned char> NFCReader::transmit(const std::vector<unsigned char>& command) {
    unsigned char response[258]{};
    DWORD length = sizeof(response);
    const SCARD_IO_REQUEST* pci = protocol_ == SCARD_PROTOCOL_T1 ? SCARD_PCI_T1 : SCARD_PCI_T0;
    LONG result = SCardTransmit(card_, pci, command.data(), static_cast<DWORD>(command.size()),
                               nullptr, response, &length);
    if (result != SCARD_S_SUCCESS) throw std::runtime_error("card_removed_or_transport_error");
    if (length < 2 || response[length - 2] != 0x90 || response[length - 1] != 0x00)
        throw std::runtime_error("unsupported_apdu_or_card_access_denied");
    return std::vector<unsigned char>(response, response + length - 2);
}

std::vector<unsigned char> NFCReader::readPages(unsigned char start) {
    // MIFARE Ultralight / NTAG: read four 4-byte pages (16 bytes).
    auto bytes = transmit({0xFF, 0xB0, 0x00, start, 0x10});
    if (bytes.size() != 16) throw std::runtime_error("unsupported_read_length");
    return bytes;
}

void NFCReader::verifyType2() {
    const auto cc = readPages(3);
    // NFC Forum Type 2 capability container. No locked/read-protected card writes.
    if (cc[0] != 0xE1 || (cc[1] >> 4) != 1 || cc[2] < 6 || cc[3] != 0x00)
        throw std::runtime_error("unsupported_or_protected_type2_card");
}

std::string NFCReader::readToken() {
    verifyType2();
    std::vector<unsigned char> data;
    for (unsigned char page : {4, 8, 12}) {
        const auto block = readPages(page);
        data.insert(data.end(), block.begin(), block.end());
    }
    if (!std::equal(std::begin(MAGIC), std::end(MAGIC), data.begin()))
        throw std::runtime_error("card_not_provisioned");
    static constexpr char HEX[] = "0123456789abcdef";
    std::string token;
    for (std::size_t i = 4; i < 36; ++i) {
        token += HEX[data[i] >> 4];
        token += HEX[data[i] & 15];
    }
    return token;
}

void NFCReader::writePage(unsigned char page, const unsigned char* bytes) {
    transmit({0xFF, 0xD6, 0x00, page, 0x04, bytes[0], bytes[1], bytes[2], bytes[3]});
}

void NFCReader::writeToken(const std::string& token) {
    if (token.size() != 64) throw std::runtime_error("invalid_token");
    unsigned char data[36]{};
    std::copy(std::begin(MAGIC), std::end(MAGIC), data);
    for (std::size_t i = 0; i < 32; ++i)
        data[i + 4] = static_cast<unsigned char>((hexNibble(token[2 * i]) << 4) | hexNibble(token[2 * i + 1]));
    verifyType2();
    if (SCardBeginTransaction(card_) != SCARD_S_SUCCESS) throw std::runtime_error("card_busy");
    try {
        // Invalidate the marker before writing: interrupted writes cannot appear valid.
        const unsigned char empty[4]{};
        writePage(4, empty);
        for (unsigned char page = 5; page <= 12; ++page) writePage(page, data + (page - 4) * 4);
        writePage(4, data);
        if (readToken() != token) throw std::runtime_error("write_verification_failed");
    } catch (...) {
        SCardEndTransaction(card_, SCARD_LEAVE_CARD);
        throw;
    }
    SCardEndTransaction(card_, SCARD_LEAVE_CARD);
}
