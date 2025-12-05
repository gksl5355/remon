package com.global17.auth_service.service;

import com.global17.auth_service.entity.AdminUser;
import com.global17.auth_service.repository.AdminUserRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;

@Service
@RequiredArgsConstructor
public class AuthService {
    
    private final AdminUserRepository adminUserRepository;
    
    public AdminUser login(String username, String password) {
        AdminUser user = adminUserRepository.findByUsername(username)
                .orElse(null);
        
        if (user == null) {
            return null;
        }
        
        // 비밀번호 검증 (평문 비교)
        if (user.getPassword().equals(password)) {
            return user;
        }
        
        return null;
    }
}
