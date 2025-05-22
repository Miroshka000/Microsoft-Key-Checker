import React from 'react';
import { Container, Row, Col, Card } from 'react-bootstrap';

const Home = () => {
  return (
    <Container>
      <Row className="mb-4">
        <Col>
          <h1>Microsoft Key Checker</h1>
          <p className="lead">
            Приложение для проверки ключей активации продуктов Microsoft с учетом региональных ограничений.
          </p>
        </Col>
      </Row>
      
      <Row>
        <Col md={4} className="mb-4">
          <Card>
            <Card.Header>Проверка ключей</Card.Header>
            <Card.Body>
              <Card.Title>Проверка ключей</Card.Title>
              <Card.Text>
                Проверяйте отдельные ключи или загружайте сразу несколько для пакетной проверки.
              </Card.Text>
            </Card.Body>
          </Card>
        </Col>
        
        <Col md={4} className="mb-4">
          <Card>
            <Card.Header>Управление аккаунтами</Card.Header>
            <Card.Body>
              <Card.Title>Аккаунты Microsoft</Card.Title>
              <Card.Text>
                Добавляйте и управляйте аккаунтами Microsoft для проверки ключей.
              </Card.Text>
            </Card.Body>
          </Card>
        </Col>
        
        <Col md={4} className="mb-4">
          <Card>
            <Card.Header>VPN соединения</Card.Header>
            <Card.Body>
              <Card.Title>Регионы и VPN</Card.Title>
              <Card.Text>
                Настраивайте VPN-соединения для проверки региональных ключей.
              </Card.Text>
            </Card.Body>
          </Card>
        </Col>
      </Row>
    </Container>
  );
};

export default Home; 