#include "NFCReader.h"
#include <iostream>
#include <stdexcept>
#include <string>

int main(int argc, char** argv) {
    try {
        bool writing = argc == 3 && std::string(argv[1]) == "--write-token-stdin" &&
                       std::string(argv[2]) == "--confirm-type2";
        if (!writing && !(argc == 2 && std::string(argv[1]) == "--read"))
            throw std::runtime_error("usage_read_or_explicit_type2_write");
        std::string token;
        if (writing) {
            std::getline(std::cin, token);
            if (token.size() != 64 || token.find_first_not_of("0123456789abcdef") != std::string::npos)
                throw std::runtime_error("invalid_token");
        }
        NFCReader reader;
        reader.connect();
        if (writing) {
            reader.writeToken(token);
            std::cout << "{\"ok\":true,\"written\":true}\n";
        } else {
            token = reader.readToken();
            std::cout << "{\"ok\":true,\"token\":\"" << token << "\",\"reader\":\"PC/SC Type2\"}\n";
        }
        return 0;
    } catch (const std::exception& error) {
        // Exceptions above are fixed safe identifiers, never arbitrary device strings.
        std::string code = error.what();
        if (code.find_first_not_of("abcdefghijklmnopqrstuvwxyz0123456789_") != std::string::npos)
            code = "unexpected_reader_error";
        std::cout << "{\"ok\":false,\"error\":\"" << code << "\"}\n";
        return 1;
    }
}
