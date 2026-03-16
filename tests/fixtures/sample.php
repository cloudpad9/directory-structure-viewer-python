<?php
class UserService {
    private $db;

    public function __construct($db) {
        $this->db = $db;
    }

    public function getUser($id) {
        return $this->db->find($id);
    }

    protected function validateEmail($email) {
        return filter_var($email, FILTER_VALIDATE_EMAIL) !== false;
    }

    private static function hashPassword($password) {
        return password_hash($password, PASSWORD_BCRYPT);
    }

    public static function createUser($name, $email, $password) {
        if (!self::validateEmail($email)) {
            throw new RuntimeException('Invalid email');
        }
        return ['name' => $name, 'email' => $email, 'password' => self::hashPassword($password)];
    }
}
