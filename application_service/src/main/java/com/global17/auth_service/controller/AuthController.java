package com.global17.auth_service.controller;

import java.util.Map;

import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.CrossOrigin;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import com.global17.auth_service.entity.AdminUser;
import com.global17.auth_service.service.AuthService;

import jakarta.servlet.http.HttpSession;
import lombok.RequiredArgsConstructor;


@RestController
@RequestMapping("/api")
@CrossOrigin(origins = "${api.base-url}", allowCredentials = "true")
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
        
        return ResponseEntity.ok(Map.of(
                "message", "Login successful",
                "username", user.getUsername(),
                "userId", user.getAdminUserId()

        ));
    }
    
    @GetMapping("/check-auth")
    public ResponseEntity<?> checkAuth(HttpSession session) {
    Integer userId = (Integer) session.getAttribute("userId");
    System.out.println("userId: "+userId);
    if (userId == null) {
        return ResponseEntity.status(401)
                .body(Map.of("message", "로그인 필요"));
    }
    
    // id가 1이면 관리자
    return ResponseEntity.ok(Map.of(
            "isAdmin", userId == 1,
            "userId", userId
    ));
}

    @PostMapping("/logout")
    public ResponseEntity<?> logout(HttpSession session) {
        session.invalidate();
        return ResponseEntity.ok(Map.of("message", "Logout successful"));
    }    

}
