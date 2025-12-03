package com.global17.auth_service.controller;

import com.global17.auth_service.entity.AdminUser;
import com.global17.auth_service.service.AuthService;
import jakarta.servlet.http.HttpSession;
import lombok.RequiredArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.Map;

@RestController
@RequestMapping("/api/auth")
@RequiredArgsConstructor
public class AuthController {
    
    private final AuthService authService;
    
    @PostMapping("/login")
    public ResponseEntity<?> login(
            @RequestBody Map<String, String> request,
            HttpSession session
    ) {
        String username = request.get("username");
        String password = request.get("password");
        
        AdminUser user = authService.login(username, password);
        
        if (user == null) {
            return ResponseEntity.status(401)
                    .body(Map.of("message", "Invalid credentials"));
        }
        
        // 세션에 사용자 정보 저장
        session.setAttribute("userId", user.getAdminUserId());
        session.setAttribute("username", user.getUsername());
        
        return ResponseEntity.ok(Map.of(
                "message", "Login successful",
                "username", user.getUsername()
        ));
    }
    
    @PostMapping("/logout")
    public ResponseEntity<?> logout(HttpSession session) {
        session.invalidate();
        return ResponseEntity.ok(Map.of("message", "Logout successful"));
    }    

}
